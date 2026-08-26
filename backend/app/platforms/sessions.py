"""Login-state storage and platform status management.

Login states are Playwright ``storage_state`` JSON blobs stored under
``data/platform_sessions/<platform>.json``. ``data/`` is gitignored (NFR-2),
so no cookies ever enter version control.

The in-memory status machine mirrors the four states agreed in the spec::

    not_logged_in | logging_in | logged_in | expired
"""
import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import settings

SUPPORTED_PLATFORMS = ("cnki", "baidu_xueshu")

NOT_LOGGED_IN = "not_logged_in"
LOGGING_IN = "logging_in"
LOGGED_IN = "logged_in"
EXPIRED = "expired"


class LoginRequiredError(Exception):
    """Raised when a search needs a platform login that is missing."""

    def __init__(self, platform: str) -> None:
        self.platform = platform
        super().__init__(f"平台 {platform} 需要登录")


class LoginExpiredError(Exception):
    """Raised when a saved login state has expired (verification page shown)."""

    def __init__(self, platform: str) -> None:
        self.platform = platform
        super().__init__(f"平台 {platform} 登录态已过期")


_STATES: Dict[str, str] = {}
_LOCK = threading.RLock()


def _sessions_dir() -> Path:
    return settings.data_dir / "platform_sessions"


def _state_path(platform: str) -> Path:
    return _sessions_dir() / f"{platform}.json"


def has_state(platform: str) -> bool:
    """Return True when a non-empty storage_state file exists for ``platform``."""
    return _state_path(platform).is_file()


def save_state(platform: str, state: Dict[str, Any]) -> None:
    """Persist a Playwright ``storage_state`` dict to disk (atomic write)."""
    _sessions_dir().mkdir(parents=True, exist_ok=True)
    path = _state_path(platform)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def load_state(platform: str) -> Optional[Dict[str, Any]]:
    """Return the saved storage_state dict, or None when missing/corrupt."""
    path = _state_path(platform)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def delete_state(platform: str) -> None:
    """Remove the saved storage_state file for ``platform``."""
    try:
        _state_path(platform).unlink(missing_ok=True)
    except OSError:
        pass


def get_state(platform: str) -> str:
    """Return the current in-memory status for ``platform``."""
    with _LOCK:
        return _STATES.get(platform, LOGGED_IN if has_state(platform) else NOT_LOGGED_IN)


def set_state(platform: str, state: str) -> None:
    """Set the in-memory status for ``platform``."""
    with _LOCK:
        _STATES[platform] = state


def list_states() -> List[Dict[str, str]]:
    """Return ``{"platform", "state"}`` entries for every supported platform."""
    return [
        {"platform": platform, "state": get_state(platform)}
        for platform in SUPPORTED_PLATFORMS
    ]


def reset_states() -> None:
    """Clear the in-memory status overrides (used by tests)."""
    with _LOCK:
        _STATES.clear()
