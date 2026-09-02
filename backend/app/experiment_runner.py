"""Experiment run pipeline executor.

Drives a 4-step pipeline (sync_code → setup_env → launch_training →
monitor_output) against a remote SSH server, streaming command output line by
line to WebSocket observers and persisting an append-only, redacted log file.
"""
import asyncio
import logging
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import paramiko

from . import database
from .config import settings
from .metrics_extractor import extract_metrics
from .redact import redact_secrets
from .ssh import connect

logger = logging.getLogger(__name__)

STEPS = ["sync_code", "setup_env", "launch_training", "monitor_output"]

COMMAND_TIMEOUT = 1800.0
RETRY_AFTER_FAILURE = 1
MONITOR_POLL_SECONDS = 2.0


def _connect(server_record: Dict[str, Any]) -> paramiko.SSHClient:
    """Create an SSH client for a server record (module-level for testability)."""
    return connect(server_record)

_PID_LINE_RE = re.compile(r"^\s*(\d+)\s*$")


def build_default_steps(workdir: str, repo_url: str = "") -> Dict[str, str]:
    sync = f"git clone {repo_url} {workdir}" if repo_url else ""
    return {
        "sync_code": sync,
        "setup_env": f"cd {workdir} && pip install -r requirements.txt",
        "launch_training": (
            f"cd {workdir} && nohup python train.py > train_output.log 2>&1 & echo $!"
        ),
        "monitor_output": f"tail -n 200 -f {workdir}/train_output.log",
    }


def _parse_pid(lines: List[str]) -> Optional[int]:
    for line in reversed(lines):
        match = _PID_LINE_RE.match(line)
        if match:
            return int(match.group(1))
    return None


def process_alive(client: paramiko.SSHClient, pid: int) -> bool:
    try:
        _stdin, stdout, _stderr = client.exec_command(f"kill -0 {pid}", timeout=10)
        return stdout.channel.recv_exit_status() == 0
    except Exception:
        return False


def _kill_pid(client: paramiko.SSHClient, pid: int) -> None:
    for sig in ("TERM", "KILL"):
        try:
            client.exec_command(f"kill -{sig} {pid}", timeout=10)
        except Exception:
            pass
        if not process_alive(client, pid):
            return
        time.sleep(1)


def _run_command_streamed(
    client: paramiko.SSHClient,
    command: str,
    on_line: Callable[[str], Any],
) -> tuple[int, List[str]]:
    """Execute ``command`` on ``client``, pushing lines to sync ``on_line``.

    Blocking; must be invoked via ``asyncio.to_thread``. Returns
    ``(exit_code, all_lines)``.
    """
    lines: List[str] = []
    transport = client.get_transport()
    if transport is None or not transport.is_active():
        raise RuntimeError("SSH 连接不可用")
    channel = transport.open_session(timeout=30)
    channel.settimeout(COMMAND_TIMEOUT)
    channel.exec_command(command)
    buffer = b""

    def _flush(final: bool) -> None:
        nonlocal buffer
        while b"\n" in buffer:
            raw, buffer = buffer.split(b"\n", 1)
            text = raw.decode("utf-8", errors="replace").rstrip("\r")
            lines.append(text)
            on_line(text)
        if final and buffer:
            text = buffer.decode("utf-8", errors="replace").rstrip("\r")
            lines.append(text)
            on_line(text)
            buffer = b""

    while True:
        if channel.recv_ready():
            data = channel.recv(4096)
            if not data:
                break
            buffer += data
            _flush(final=False)
        elif channel.exit_status_ready():
            # The command finished, but data may still be in flight: drain
            # until recv_ready() goes quiet before returning.
            drained_empty = False
            while not drained_empty:
                drained_empty = True
                deadline = time.monotonic() + 1.0
                while time.monotonic() < deadline:
                    if channel.recv_ready():
                        data = channel.recv(4096)
                        if data:
                            buffer += data
                            drained_empty = False
                            break
                    time.sleep(0.02)
            _flush(final=True)
            break
        else:
            time.sleep(0.05)
    exit_code = channel.recv_exit_status()
    return exit_code, lines


def _threadsafe(loop: asyncio.AbstractEventLoop, coro) -> None:
    """Schedule a coroutine on the loop and wait for it from a worker thread."""
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    try:
        future.result(timeout=10)
    except Exception:
        pass


def _log_path(run_id: int) -> Path:
    return Path(settings.data_dir / "experiment_runs" / f"{run_id}.log")


def run_log_path(run_id: int) -> Path:
    """Canonical local log file location for a run (public helper)."""
    return _log_path(run_id)


def extract_and_store_metrics(run_id: int) -> Dict[str, float]:
    """Parse the run's local log and persist extracted metrics (spec-038 FR-2).

    Uses the recorded ``log_path`` when present, falling back to the canonical
    ``data/experiment_runs/{run_id}.log`` location.
    """
    record = database.get_experiment_run(run_id) or {}
    log_path = record.get("log_path") or str(_log_path(run_id))
    metrics = extract_metrics(log_path)
    database.set_experiment_run_metrics(run_id, metrics)
    return metrics


_log_locks: Dict[int, asyncio.Lock] = {}
_log_locks_guard = threading.Lock()


def _log_lock(run_id: int) -> asyncio.Lock:
    with _log_locks_guard:
        lock = _log_locks.get(run_id)
        if lock is None:
            lock = asyncio.Lock()
            _log_locks[run_id] = lock
        return lock


async def append_log(run_id: int, text: str) -> None:
    """Append redacted ``text`` to the run's log file (serialised per run)."""
    path = _log_path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    async with _log_lock(run_id):
        def _write() -> None:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(redact_secrets(text) + "\n")

        await asyncio.to_thread(_write)


def read_log_tail(run_id: int, n: int = 200) -> str:
    path = _log_path(run_id)
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-n:])


def delete_log(run_id: int) -> None:
    path = _log_path(run_id)
    path.unlink(missing_ok=True)


class ExperimentRunDriver:
    """Owns the asyncio task driving one experiment run's step pipeline."""

    def __init__(self, run_id: int) -> None:
        self.run_id = run_id
        self.task: Optional[asyncio.Task] = None
        self.observers: set = set()
        self.steps: Dict[str, str] = {}
        self._stop_requested = False
        self._lock = threading.Lock()

    # ---- observer plumbing -------------------------------------------------
    def attach(self, callback) -> None:
        self.observers.add(callback)

    def detach(self, callback) -> None:
        self.observers.discard(callback)

    async def _emit(self, event: Dict[str, Any]) -> None:
        for callback in list(self.observers):
            try:
                result = callback(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass

    async def _emit_status(self, status: str, error: Optional[str] = None) -> None:
        database.update_experiment_run(self.run_id, status=status, error=error)
        event: Dict[str, Any] = {"type": "status", "status": status}
        if error:
            event["error"] = error
        await self._emit(event)

    async def _emit_step(self, step: str, status: str, error: Optional[str] = None) -> None:
        database.update_experiment_run(self.run_id, current_step=step)
        event: Dict[str, Any] = {"type": "step", "step": step, "status": status}
        if error:
            event["error"] = error
        await self._emit(event)

    # ---- lifecycle ---------------------------------------------------------
    @staticmethod
    def get(run_id: int) -> Optional["ExperimentRunDriver"]:
        return _drivers.get(run_id)

    @staticmethod
    def get_or_create(run_id: int) -> "ExperimentRunDriver":
        with _drivers_lock:
            driver = _drivers.get(run_id)
            if driver is None:
                driver = ExperimentRunDriver(run_id)
                _drivers[run_id] = driver
            return driver

    @staticmethod
    def stop(run_id: int) -> bool:
        driver = _drivers.get(run_id)
        if driver is None:
            return False
        driver.request_stop()
        return True

    # ---- execution ---------------------------------------------------------
    def start(self, steps: Dict[str, str]) -> None:
        with self._lock:
            if self.task is not None and not self.task.done():
                raise RuntimeError("该运行已在执行中")
            self.steps = dict(steps)
            record = database.get_experiment_run(self.run_id)
            if record is None:
                raise ValueError("运行记录不存在")

            async def runner() -> None:
                from . import servers as servers_module

                server_record = servers_module.get_server(record["server_id"])
                if server_record is None:
                    await self._emit_status("failed", "服务器不存在")
                    return
                try:
                    await self._pipeline(server_record)
                except asyncio.CancelledError:
                    if self._stop_requested:
                        await self._emit_status("stopped")
                    raise
                except Exception as exc:  # noqa: BLE001 - surface to UI
                    logger.error(
                        "实验管线异常: run=%s", self.run_id, exc_info=exc
                    )
                    await self._emit_status("failed", redact_secrets(str(exc)))

            self.task = asyncio.create_task(runner())

    def request_stop(self) -> None:
        self._stop_requested = True
        task = self.task
        if task is not None and not task.done():
            task.cancel()

    async def kill_remote(self, pid: Optional[int]) -> None:
        if not pid:
            return
        record = database.get_experiment_run(self.run_id)
        if record is None:
            return
        from . import servers as servers_module

        server = servers_module.get_server(record["server_id"])
        if server is None:
            return
        client = await asyncio.to_thread(connect, server)
        try:
            await asyncio.to_thread(_kill_pid, client, pid)
        finally:
            client.close()

    async def stop_run(self) -> None:
        record = database.get_experiment_run(self.run_id)
        pid = record.get("pid") if record else None
        await self.kill_remote(pid)
        self.request_stop()
        # If no task is alive (e.g. paused), still mark stopped.
        if self.task is None or self.task.done():
            await self._emit_status("stopped")

    # ---- step helpers ------------------------------------------------------
    def _resolve_client(self, server_record: Dict[str, Any]) -> paramiko.SSHClient:
        return _connect(server_record)

    async def _execute_step(
        self,
        server_record: Dict[str, Any],
        step: str,
        command: str,
    ) -> bool:
        if not command.strip():
            await self._emit(
                {"type": "log", "line": f"[{step}] 无命令，跳过执行内容", "stream": "stdout"}
            )
            return True
        loop = asyncio.get_event_loop()

        def on_line(line: str) -> None:
            _threadsafe(loop, self._emit({"type": "log", "line": line, "stream": "stdout"}))
            _threadsafe(loop, append_log(self.run_id, line))

        for attempt in range(RETRY_AFTER_FAILURE + 1):
            await self._emit_step(step, "running")
            client = await asyncio.to_thread(self._resolve_client, server_record)
            try:
                exit_code, lines = await asyncio.to_thread(
                    _run_command_streamed, client, command, on_line
                )
            except Exception as exc:  # noqa: BLE001
                exit_code, lines = 1, [f"[本地异常] {exc}"]
            finally:
                try:
                    client.close()
                except Exception:
                    pass

            if exit_code == 0:
                if step == "launch_training":
                    pid = _parse_pid(lines)
                    if pid:
                        database.update_experiment_run(self.run_id, pid=pid)
                        await self._emit({"type": "log", "line": f"[PID] {pid}", "stream": "stdout"})
                logger.info("实验步骤成功: run=%s step=%s", self.run_id, step)
                await self._emit_step(step, "success")
                return True
            if attempt < RETRY_AFTER_FAILURE:
                await self._emit_step(step, "retrying")
                await asyncio.sleep(1.0)
        logger.warning(
            "实验步骤失败: run=%s step=%s", self.run_id, step
        )
        await self._emit_step(step, "failed", "\n".join(lines[-5:]))
        return False

    async def _pipeline(self, server_record: Dict[str, Any]) -> None:
        resume_from = getattr(self, "_resume_from", None) or STEPS[0]
        index = STEPS.index(resume_from)
        logger.info(
            "实验管线开始: run=%s step=%d/%d (%s)",
            self.run_id, index + 1, len(STEPS), resume_from,
        )
        for step in STEPS[index:]:
            if getattr(self, "_skip_steps", None) and step in self._skip_steps:
                await self._emit_step(step, "skipped")
                continue
            if step == "monitor_output":
                # The monitor is a polling loop (not a one-shot command): tail
                # the training log incrementally and finish when the recorded
                # pid exits. Emits/logs every new line, so the run log ends up
                # containing the full training output.
                await self._emit_step(step, "running")
                ok = await self._monitor_loop(server_record)
                if ok:
                    await self._emit_step(step, "success")
                else:
                    logger.warning("实验管线暂停: run=%s step=%s", self.run_id, step)
                    await self._emit_status("paused", f"步骤 {step} 执行失败")
                return
            ok = await self._execute_step(server_record, step, self.steps.get(step, ""))
            if not ok:
                logger.warning("实验管线暂停: run=%s step=%s", self.run_id, step)
                await self._emit_status("paused", f"步骤 {step} 执行失败")
                return
        await self._emit_status("running")

    async def _monitor_loop(self, server_record: Dict[str, Any]) -> bool:
        """Tail the remote training log until the launched pid exits."""
        record = database.get_experiment_run(self.run_id) or {}
        pid = record.get("pid")
        workdir = (record.get("remote_workdir") or "~").rstrip("/")
        log_file = f"{workdir}/train_output.log"
        offset = 0
        idle_rounds = 0
        while True:
            client = await asyncio.to_thread(self._resolve_client, server_record)
            try:
                # Drain new log content since last offset.
                command = (
                    f"tail -c +{offset + 1} {log_file} 2>/dev/null; "
                    f"echo __EXIT__$(test -n {pid} && kill -0 {pid} 2>/dev/null; echo $?)"
                    if pid
                    else f"tail -c +{offset + 1} {log_file} 2>/dev/null; echo __EXIT__9"
                )
                exit_code, lines = await asyncio.to_thread(
                    _run_command_streamed, client, command, lambda line: None
                )
            except Exception as exc:  # noqa: BLE001
                await self._emit(
                    {"type": "log", "line": f"[monitor 本地异常] {exc}", "stream": "stdout"}
                )
                return False
            finally:
                try:
                    client.close()
                except Exception:
                    pass

            alive_marker = next(
                (l for l in reversed(lines) if l.startswith("__EXIT__")), None
            )
            content_lines = [l for l in lines if not l.startswith("__EXIT__")]
            new_bytes = sum(len(l.encode("utf-8")) + 1 for l in content_lines)
            if new_bytes > 0:
                offset += new_bytes
                idle_rounds = 0
                for line in content_lines:
                    await append_log(self.run_id, line)
                    await self._emit({"type": "log", "line": line, "stream": "stdout"})
            else:
                idle_rounds += 1

            alive = alive_marker == "__EXIT__0" if pid else False
            if pid and alive_marker not in ("__EXIT__0", "__EXIT__1"):
                alive = False
            if not alive:
                if pid is None and idle_rounds < 15:
                    # No pid recorded: fall back to waiting until the log stops
                    # growing for ~30s before declaring completion.
                    await asyncio.sleep(MONITOR_POLL_SECONDS)
                    continue
                await self._emit(
                    {
                        "type": "log",
                        "line": "[monitor] 训练进程已退出，抓取最终日志…",
                        "stream": "stdout",
                    }
                )
                await self._emit_status("succeeded")
                try:
                    extract_and_store_metrics(self.run_id)
                except Exception:  # noqa: BLE001 - metrics must not break the run
                    logger.warning(
                        "metrics 自动提取失败: run=%s", self.run_id, exc_info=True
                    )
                return True
            await asyncio.sleep(MONITOR_POLL_SECONDS)

    # ---- control from paused state ----------------------------------------
    def resume_with_action(self, action: str, step: str, command: str = "") -> None:
        with self._lock:
            if self.task is not None and not self.task.done():
                raise RuntimeError("任务仍在运行")
            if action == "retry":
                self.steps[step] = command or self.steps.get(step, "")
                self._resume_from = step
                self._skip_steps = set()
            elif action == "skip":
                self._resume_from = step
                self._skip_steps = {step}
            else:
                raise ValueError(f"未知操作: {action}")
            record = database.get_experiment_run(self.run_id)

            async def runner() -> None:
                from . import servers as servers_module

                if record is None:
                    return
                server_record = servers_module.get_server(record["server_id"])
                if server_record is None:
                    await self._emit_status("failed", "服务器不存在")
                    return
                try:
                    await self._pipeline(server_record)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    await self._emit_status("failed", redact_secrets(str(exc)))

            self.task = asyncio.create_task(runner())


_drivers: Dict[int, ExperimentRunDriver] = {}
_drivers_lock = threading.Lock()
