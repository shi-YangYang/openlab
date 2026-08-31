"""Agent permission engine (spec-032).

A single global mode decides whether the 10 "dangerous" tools need user
approval or execute automatically:

- ``conservative``: every dangerous tool asks for approval (old behaviour).
- ``standard`` (default): local sandbox tools (``run_python_code`` /
  ``run_shell_command``) and whitelisted read-only ``run_command`` calls
  execute automatically; everything else asks.
- ``full``: everything auto-executes.

A hardcoded safety floor can never be bypassed in any mode: the
``delete_server`` tool and destructive command patterns always ask (FR-2).
``evaluate`` is a pure function so the decision matrix is unit-testable
(NFR-4); persistence lives in ``backend/data/agent_permissions.json``
(gitignored, same policy as ``llm_config.json``).
"""
import json
import logging
import os
from datetime import datetime
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from ..config import settings

logger = logging.getLogger(__name__)

PERMISSIONS_FILENAME = "agent_permissions.json"

MODES = ("conservative", "standard", "full")
DEFAULT_MODE = "standard"
SESSION_SCOPE = "session"
ONCE_SCOPE = "once"

ALLOW = "allow"
ASK = "ask"

# Safety floor: never auto-approved in any mode; not configurable (FR-2).
FORBIDDEN_TOOLS = {"delete_server"}

# Destructive command patterns matched (fnmatch, case-insensitive) against the
# full command string of ``run_command`` / ``run_shell_command`` in every mode.
FORBIDDEN_COMMAND_PATTERNS = [
    "rm -rf /*",
    "rm -rf ~*",
    "mkfs*",
    "dd if=*",
    "shutdown*",
    "reboot*",
    "halt*",
    "init 0",
    "init 6",
    "poweroff*",
    "chmod -R 777 /*",
    "* > /dev/sd*",
    "fdisk*",
    "wipefs*",
    ":(){*",
]

# Default read-only whitelist for ``run_command`` in standard mode (FR-4).
DEFAULT_COMMAND_WHITELIST = [
    "nvidia-smi*",
    "nvcc *",
    "pwd",
    "whoami",
    "ls*",
    "cat *",
    "head *",
    "tail *",
    "df*",
    "free*",
    "du *",
    "ps *",
    "which *",
    "echo *",
    "python *--version",
    "pip list*",
    "pip show *",
    "pip freeze*",
    "git status*",
    "git log*",
    "git diff*",
    "git branch",
    "git show*",
    "git remote -v",
]

# Tools whose ``command`` argument is matched against the black/white lists.
COMMAND_TOOLS = {"run_command", "run_shell_command"}

# Local sandbox tools auto-approved in standard mode (FR-1).
LOCAL_SANDBOX_TOOLS = {"run_python_code", "run_shell_command"}

# Commands containing any of these operators never match the whitelist (FR-5).
COMPOSITE_OPERATORS = (";", "&&", "||", "|")


def _permissions_path() -> Path:
    return Path(
        os.getenv(
            "AGENT_PERMISSIONS_PATH",
            str(settings.data_dir / PERMISSIONS_FILENAME),
        )
    )


def default_state() -> Dict[str, Any]:
    return {
        "mode": DEFAULT_MODE,
        "command_whitelist": list(DEFAULT_COMMAND_WHITELIST),
    }


def _normalize_whitelist(raw: Any) -> List[str]:
    """Keep string entries only; strip, drop empties and duplicates (FR-12)."""
    if not isinstance(raw, list):
        return list(DEFAULT_COMMAND_WHITELIST)
    result: List[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if text and text not in result:
            result.append(text)
    return result


def _normalize_state(data: Any) -> Dict[str, Any]:
    mode = data.get("mode") if isinstance(data, dict) else None
    if mode not in MODES:
        mode = DEFAULT_MODE
    whitelist = data.get("command_whitelist") if isinstance(data, dict) else None
    return {"mode": mode, "command_whitelist": _normalize_whitelist(whitelist)}


def _write(payload: Dict[str, Any]) -> None:
    path = _permissions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load() -> Dict[str, Any]:
    """Return ``{mode, command_whitelist, updated_at}``.

    A missing file falls back to the defaults (NFR-3); a corrupt file falls
    back to the defaults and is rebuilt (FR-6 / AC-4). ``updated_at`` is
    ``None`` until the first save. The file is read on every call so mode
    changes apply to the next tool call globally (FR-14).
    """
    path = _permissions_path()
    if not path.exists():
        state = default_state()
        try:
            _write({"updated_at": None, **state})
        except OSError:
            pass
        return {**state, "updated_at": None}
    data: Any = None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        state = _normalize_state(data)
    except (json.JSONDecodeError, OSError, AttributeError):
        # Corrupt file: fall back to defaults and rebuild it (FR-6 / AC-4).
        state = default_state()
        try:
            _write({"updated_at": None, **state})
        except OSError:
            pass
        data = None
    updated_at = data.get("updated_at") if isinstance(data, dict) else None
    return {**state, "updated_at": updated_at if isinstance(updated_at, str) else None}


def save(mode: str, command_whitelist: Iterable[Any]) -> Dict[str, Any]:
    """Validate and persist ``{mode, command_whitelist, updated_at}`` (FR-12)."""
    if mode not in MODES:
        raise ValueError(
            "mode 必须是 conservative / standard / full 之一"
        )
    payload = {
        "mode": mode,
        "command_whitelist": _normalize_whitelist(list(command_whitelist)),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _write(payload)
    logger.info(
        "权限配置更新: mode=%s whitelist=%d 项", payload["mode"],
        len(payload["command_whitelist"]),
    )
    return payload


def reset() -> Dict[str, Any]:
    """Restore defaults: standard mode + default whitelist (FR-13)."""
    return save(DEFAULT_MODE, DEFAULT_COMMAND_WHITELIST)


def command_from_args(args: Any) -> Optional[str]:
    """Extract the command string from tool args (``run_*`` tools)."""
    if not isinstance(args, dict):
        return None
    command = args.get("command")
    if isinstance(command, str) and command.strip():
        return command
    return None


def is_composite_command(command: str) -> bool:
    return any(op in command for op in COMPOSITE_OPERATORS)


def matches_forbidden_command(command: str) -> bool:
    lowered = command.lower()
    return any(
        fnmatchcase(lowered, pattern.lower())
        for pattern in FORBIDDEN_COMMAND_PATTERNS
    )


def matches_whitelist(command: str, whitelist: Iterable[str]) -> bool:
    if is_composite_command(command):
        return False
    return any(fnmatchcase(command, pattern) for pattern in whitelist)


def evaluate(
    tool: str,
    args: Any,
    mode: str = DEFAULT_MODE,
    whitelist: Optional[Iterable[str]] = None,
    session_allows: Optional[Set[str]] = None,
) -> str:
    """Pure decision function: ``allow`` (auto-execute) or ``ask`` (approve).

    Priority, highest first (FR-3):

    1. tool blacklist (``delete_server``) → ``ask``
    2. forbidden command pattern hit → ``ask``
    3. ``mode == "full"`` → ``allow``
    4. session-level allow set → ``allow``
    5. ``mode == "standard"``: local sandbox tools / whitelisted command → ``allow``
    6. otherwise (incl. ``conservative``) → ``ask``
    """
    if tool in FORBIDDEN_TOOLS:
        return ASK

    command = command_from_args(args)
    if tool in COMMAND_TOOLS and command and matches_forbidden_command(command):
        return ASK

    if mode == "full":
        return ALLOW

    if session_allows and tool in session_allows:
        return ALLOW

    if mode == "standard":
        if tool in LOCAL_SANDBOX_TOOLS:
            return ALLOW
        if tool == "run_command" and command:
            if matches_whitelist(command, whitelist or []):
                return ALLOW
    return ASK
