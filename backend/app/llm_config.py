"""LLM configuration persistence and resolution.

The LLM configuration (``base_url`` / ``api_key`` / ``model``) can be saved to
a local JSON file (default ``backend/data/llm_config.json``). ``data/`` is
gitignored, so the file never enters version control; the API key is never
stored in SQLite and never hardcoded or logged.

Resolution priority for each field is, in order:

1. local config file (``LLM_CONFIG_PATH`` or ``backend/data/llm_config.json``),
2. environment variable (``LLM_BASE_URL`` / ``LLM_API_KEY`` / ``LLM_MODEL``),
3. built-in default.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .config import settings

CONFIG_FILENAME = "llm_config.json"

_VALID_KEYS = ("base_url", "api_key", "model")

_DEFAULTS = {
    "base_url": "https://api.openai.com/v1",
    "api_key": "",
    "model": "gpt-4o-mini",
}


def _config_path() -> Path:
    return Path(
        os.getenv("LLM_CONFIG_PATH", str(settings.data_dir / CONFIG_FILENAME))
    )


def _clean(data: Dict[str, Any]) -> Dict[str, str]:
    return {
        key: str(data[key])
        for key in _VALID_KEYS
        if isinstance(data.get(key), str)
    }


def load_config() -> Dict[str, str]:
    """Return the raw local config file contents (only known keys)."""
    path = _config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return _clean(data)


def save_config(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, str]:
    """Persist the provided fields, preserving any unspecified ones."""
    current = load_config()
    if base_url is not None:
        current["base_url"] = base_url
    if api_key is not None:
        current["api_key"] = api_key
    if model is not None:
        current["model"] = model

    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return current


def get_effective_config() -> Dict[str, str]:
    """Resolve the effective config (local file -> env -> default)."""
    local = load_config()
    return {
        "base_url": (
            local.get("base_url")
            or os.getenv("LLM_BASE_URL")
            or _DEFAULTS["base_url"]
        ).rstrip("/"),
        "api_key": local.get("api_key") or os.getenv("LLM_API_KEY") or _DEFAULTS["api_key"],
        "model": local.get("model") or os.getenv("LLM_MODEL") or _DEFAULTS["model"],
    }
