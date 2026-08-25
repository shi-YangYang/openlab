from pathlib import Path

import pytest

from app import config, database
from app.agent import sandbox


@pytest.fixture(autouse=True)
def _setup(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config.settings, "data_dir", data_dir)
    monkeypatch.setattr(config.settings, "papers_dir", data_dir / "papers")
    monkeypatch.setattr(config.settings, "db_path", data_dir / "openlab.db")
    database.init_db()
    yield


def test_sandbox_dir_created_and_per_session():
    d1 = sandbox.sandbox_dir("s1")
    d2 = sandbox.sandbox_dir("s2")
    assert d1.is_dir()
    assert d2.is_dir()
    assert d1 != d2
    assert d1 == config.settings.data_dir / "sandbox" / "s1"
    assert d2 == config.settings.data_dir / "sandbox" / "s2"


def test_run_python_returns_stdout():
    res = sandbox.run_python("print('hello-sandbox')", "s1")
    assert res["returncode"] == 0
    assert res["stdout"].strip() == "hello-sandbox"
    assert res["stderr"] == ""


def test_run_python_cwd_is_sandbox_dir():
    res = sandbox.run_python("import os; print(os.getcwd())", "s1")
    assert res["returncode"] == 0
    assert Path(res["stdout"].strip()).resolve() == sandbox.sandbox_dir("s1").resolve()


def test_run_python_directory_isolation():
    res = sandbox.run_python("open('out.txt', 'w').write('hi')", "s1")
    assert res["returncode"] == 0
    assert (sandbox.sandbox_dir("s1") / "out.txt").read_text() == "hi"
    assert not (sandbox.sandbox_dir("s2") / "out.txt").exists()


def test_run_shell_returns_output():
    res = sandbox.run_shell("echo hello-shell", "s1")
    assert res["returncode"] == 0
    assert "hello-shell" in res["stdout"]


def test_run_shell_cwd_is_sandbox_dir():
    res = sandbox.run_python("import os; print(os.getcwd())", "s1")
    cwd = Path(res["stdout"].strip()).resolve()
    assert cwd == sandbox.sandbox_dir("s1").resolve()


def test_timeout_returns_error():
    res = sandbox.run_python("import time; time.sleep(5)", "s1", timeout=0.2)
    assert res["returncode"] is None
    assert res.get("error") == "timeout"
    assert "超时" in res["stderr"]


def test_no_secret_env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-secret-value")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws-secret-value")
    res = sandbox.run_python(
        "import os; print(os.environ.get('LLM_API_KEY'), os.environ.get('AWS_SECRET_ACCESS_KEY'))",
        "s1",
    )
    assert res["returncode"] == 0
    assert res["stdout"].strip() == "None None"


def test_allowed_env_whitelist():
    env = sandbox._allowed_env(
        {
            "PATH": "/usr/bin",
            "HOME": "/home/u",
            "LLM_API_KEY": "sk-secret",
            "SECRET_TOKEN": "secret",
        }
    )
    assert env["PATH"] == "/usr/bin"
    assert env["HOME"] == "/home/u"
    assert "LLM_API_KEY" not in env
    assert "SECRET_TOKEN" not in env


def test_run_python_returns_stderr_on_error():
    res = sandbox.run_python("raise RuntimeError('boom')", "s1")
    assert res["returncode"] != 0
    assert "boom" in res["stderr"]


def test_run_shell_nonzero_exit():
    res = sandbox.run_shell("nonexistent_command_xyz_123", "s1")
    assert res["returncode"] != 0
