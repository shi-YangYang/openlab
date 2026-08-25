"""Lightweight per-session subprocess sandbox.

The agent can run ad-hoc Python code and local shell commands (spec-012 FR-4/5).
Isolation is deliberately light: each session gets its own working directory,
commands run as a subprocess with a 60s timeout, and the child environment is
restricted to a safe whitelist (no API keys / SSH credentials are inherited).

The ``Sandbox`` class is the replaceable abstraction; swapping in a
container-based backend (e.g. Docker) later only requires reimplementing
``run_python`` / ``run_shell`` / ``sandbox_dir``.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from ..config import settings

SANDBOX_TIMEOUT_SECONDS = 60.0

# Environment variables considered safe to forward to the child process.
_ALLOWED_ENV_KEYS = (
    "PATH",
    "HOME",
    "USER",
    "SHELL",
    "LANG",
    "LC_ALL",
    "TMPDIR",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
    "PATHEXT",
    "COMSPEC",
    "SystemDrive",
    "TZ",
)


def _allowed_env(environ: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Return a whitelist-filtered environment (no secrets)."""
    source = os.environ if environ is None else environ
    return {key: source[key] for key in _ALLOWED_ENV_KEYS if source.get(key)}


class Sandbox:
    def __init__(self, timeout: float = SANDBOX_TIMEOUT_SECONDS) -> None:
        self.timeout = timeout

    def sandbox_dir(self, session_id: str) -> Path:
        path = settings.data_dir / "sandbox" / str(session_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def run_python(
        self, code: str, session_id: str, timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        command = [sys.executable, "-c", code]
        return self._run(command, session_id, timeout, shell=False)

    def run_shell(
        self, command: str, session_id: str, timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        return self._run(command, session_id, timeout, shell=True)

    def _run(
        self,
        command: Any,
        session_id: str,
        timeout: Optional[float],
        shell: bool,
    ) -> Dict[str, Any]:
        cwd = self.sandbox_dir(session_id)
        effective_timeout = self.timeout if timeout is None else timeout
        env = _allowed_env()
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd),
                timeout=effective_timeout,
                capture_output=True,
                text=True,
                env=env,
                shell=shell,
            )
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": f"执行超时（>{effective_timeout} 秒）",
                "returncode": None,
                "error": "timeout",
            }
        except Exception as exc:  # noqa: BLE001 - sandbox must not raise into the loop
            return {
                "stdout": "",
                "stderr": str(exc),
                "returncode": None,
                "error": str(exc),
            }
        return {
            "stdout": completed.stdout or "",
            "stderr": completed.stderr or "",
            "returncode": completed.returncode,
        }


_default_sandbox = Sandbox()


def sandbox_dir(session_id: str) -> Path:
    return _default_sandbox.sandbox_dir(session_id)


def run_python(
    code: str, session_id: str, timeout: Optional[float] = None
) -> Dict[str, Any]:
    return _default_sandbox.run_python(code, session_id, timeout)


def run_shell(
    command: str, session_id: str, timeout: Optional[float] = None
) -> Dict[str, Any]:
    return _default_sandbox.run_shell(command, session_id, timeout)


def delete_sandbox(session_id: str) -> None:
    """Remove a session's sandbox directory, if it exists."""
    shutil.rmtree(str(settings.data_dir / "sandbox" / str(session_id)), ignore_errors=True)


def clear_all_sandboxes() -> None:
    """Remove the entire sandbox root directory."""
    shutil.rmtree(str(settings.data_dir / "sandbox"), ignore_errors=True)
