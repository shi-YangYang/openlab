"""Tests for the experiment run pipeline executor (mocked SSH)."""
import asyncio
import json

import pytest

from app import config, database, experiment_runner
from app.experiment_runner import (
    ExperimentRunDriver,
    build_default_steps,
    _parse_pid,
)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "db_path", tmp_path / "test.db")
    database.init_db()
    yield


@pytest.fixture
def fake_server(tmp_path, monkeypatch):
    """Provide a server record and stub out real SSH connect."""
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config.settings, "data_dir", data_dir)
    import app.servers as servers

    server = {
        "id": "srv1",
        "name": "GPU",
        "host": "h",
        "port": 22,
        "username": "u",
        "auth_type": "password",
        "password": "pw-secret-1234",
    }
    monkeypatch.setattr(servers, "get_server", lambda sid: dict(server) if sid == "srv1" else None)
    monkeypatch.setattr(experiment_runner, "_connect", lambda record: FakeSSH())
    return server


class FakeChannel:
    def __init__(self, lines, exit_code=0, delay=0.0):
        self._lines = [line.encode() + b"\n" for line in lines]
        self._exit = exit_code
        self.buffer = b"".join(self._lines)

    def settimeout(self, t):
        pass

    def exec_command(self, command):
        pass

    def recv_ready(self):
        return bool(self.buffer)

    def recv(self, n):
        out, self.buffer = self.buffer[:n], self.buffer[n:]
        return out

    def exit_status_ready(self):
        return not self.buffer

    def recv_exit_status(self):
        return self._exit


class FakeSSH:
    """Scripted SSH client: each exec_command pops (lines, exit) from script."""

    def __init__(self, script):
        self.script = list(script)
        self.calls: list[str] = []
        self._current = None

    class _Transport:
        def __init__(self, ssh):
            self._ssh = ssh

        def is_active(self):
            return True

        def open_session(self, timeout=30):
            lines, exit_code = (
                self._ssh.script.pop(0) if self._ssh.script else (["ok"], 0)
            )
            return FakeChannel(lines, exit_code)

    def get_transport(self):
        return FakeSSH._Transport(self)

    def close(self):
        pass


def _seed_run(mode="manual") -> int:
    rec = database.create_experiment_run(
        experiment_id=1, server_id="srv1", mode=mode
    )
    return rec["id"]


def test_parse_pid_takes_last_numeric_line():
    assert _parse_pid(["launching", "", "12345"]) == 12345
    assert _parse_pid([]) is None


def test_build_default_steps_contains_expected_keys():
    steps = build_default_steps("/tmp/exp", "https://github.com/x/y")
    for key in ("sync_code", "setup_env", "launch_training"):
        assert key in steps


def test_successful_pipeline_completes(fake_server):
    run_id = _seed_run()
    driver = ExperimentRunDriver(run_id)

    ssh = FakeSSH([
        (["installed"], 0),
        (["12345"], 0),   # launch prints PID
        (["epoch 1 loss 0.5", "epoch 2 loss 0.3", "__EXIT__1"], 0),  # monitor: log + pid gone
    ])
    experiment_runner._connect = lambda record: ssh

    events = []
    driver.attach(lambda e: events.append(e))

    async def main():
        driver.start(build_default_steps("/tmp/exp"))
        for _ in range(400):
            await asyncio.sleep(0.05)
            rec = database.get_experiment_run(run_id)
            if rec["status"] in ("succeeded", "running", "paused", "failed"):
                if rec["status"] == "running":
                    continue  # monitor still polling; wait for pid-exit detection
                break

    asyncio.run(main())

    rec = database.get_experiment_run(run_id)
    print("EVENTS:", [(e.get("type"), e.get("step"), e.get("status"), (e.get("error") or "")[:60]) for e in events])
    assert rec["status"] == "succeeded"
    assert rec["pid"] == 12345
    types = [(e.get("type"), e.get("step"), e.get("status")) for e in events]
    assert ("step", "monitor_output", "success") in types
    # monitor lines must land in the run log
    log_text = experiment_runner.read_log_tail(run_id)
    assert "epoch 2 loss 0.3" in log_text


def test_failure_after_retry_pauses(fake_server):
    run_id = _seed_run()
    driver = ExperimentRunDriver(run_id)
    ssh = FakeSSH([
        (["boom"], 1),
        ([], 0),
        ([], 0),
    ])

    async def fail_connect(record):
        raise RuntimeError("cannot connect: boom")

    experiment_runner._connect = fail_connect

    async def main():
        driver.start(build_default_steps("/tmp/exp"))
        for _ in range(200):
            await asyncio.sleep(0.05)
            rec = database.get_experiment_run(run_id)
            if rec["status"] in ("paused", "failed", "running"):
                break

    asyncio.run(main())

    rec = database.get_experiment_run(run_id)
    assert rec["status"] == "paused"
    assert rec["error"]


def test_skip_step_marks_skipped(tmp_path):
    run_id = _seed_run()
    driver = ExperimentRunDriver(run_id)

    async def main():
        await driver._emit_step("sync_code", "skipped")
        rec = database.get_experiment_run(run_id)
        assert rec["current_step"] == "sync_code"

    asyncio.run(main())


def test_log_file_written_and_redacted(tmp_path, monkeypatch):
    from app import redact as redact_module

    monkeypatch.setattr(
        redact_module,
        "get_effective_config",
        lambda: {"base_url": "https://x", "api_key": "sk-logkey123", "model": "m"},
    )
    run_id = _seed_run()

    async def main():
        await experiment_runner.append_log(run_id, "token sk-logkey123 leaked")
        await experiment_runner.append_log(run_id, "normal line")

    asyncio.run(main())
    text = experiment_runner.read_log_tail(run_id)
    assert "sk-logkey123" not in text
    assert "leaked" in text
    assert "normal line" in text
