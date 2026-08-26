"""LLM configuration persistence and resolution.

The LLM configuration is stored as a list of "groups" in a local JSON file
(default ``backend/data/llm_config.json``). Each group describes one
OpenAI-compatible endpoint (``base_url`` / ``api_key`` / ``models`` /
``default_model``), and ``active_group`` marks which one is currently in use.
Each ``models`` entry is an object (``id`` / ``context_length`` /
``reasoning_efforts``). ``data/`` is gitignored, so the file never enters
version control; the API key is never stored in SQLite and never hardcoded or
logged.

Resolution priority for each field is, in order:

1. the active group in the local config file
   (``LLM_CONFIG_PATH`` or ``backend/data/llm_config.json``),
2. environment variable (``LLM_BASE_URL`` / ``LLM_API_KEY`` / ``LLM_MODEL`` /
   ``LLM_REASONING_EFFORT``),
3. built-in default.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import settings

CONFIG_FILENAME = "llm_config.json"

_DEFAULTS = {
    "base_url": "https://api.openai.com/v1",
    "api_key": "",
    "model": "gpt-4o-mini",
    "reasoning_effort": "",
}


def _config_path() -> Path:
    return Path(
        os.getenv("LLM_CONFIG_PATH", str(settings.data_dir / CONFIG_FILENAME))
    )


def _load_raw() -> Optional[Dict[str, Any]]:
    path = _config_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _write(payload: Dict[str, Any]) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _as_optional_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _as_reasoning_efforts(value: Any) -> List[str]:
    """Normalize a reasoning-effort value to an ordered list of strings.

    Accepts the new list form, the legacy single-string form (a non-empty
    string becomes a one-element list) and returns ``[]`` for empty/unknown.
    """
    if isinstance(value, list):
        result: List[str] = []
        for item in value:
            text = str(item).strip()
            if text and text not in result:
                result.append(text)
        return result
    text = str(value).strip() if value is not None else ""
    return [text] if text else []


def _normalize_group(group: Any) -> Optional[Dict[str, Any]]:
    """Coerce a raw group dict to known fields; ``None`` for non-dicts.

    ``models`` is normalized to a list of model entries
    (``{id, context_length, reasoning_efforts}``). Legacy string entries are
    converted to objects, and a group-level ``reasoning_effort`` is moved onto
    the default model entry (then dropped from the group).
    """
    if not isinstance(group, dict):
        return None
    gid = str(group.get("id") or "").strip()
    group_reasoning_efforts = _as_reasoning_efforts(group.get("reasoning_effort"))

    models_raw = group.get("models")
    if isinstance(models_raw, str):
        raw_models = [m.strip() for m in models_raw.split(",") if m.strip()]
    elif isinstance(models_raw, list):
        raw_models = models_raw
    else:
        raw_models = []

    models: List[Dict[str, Any]] = []
    for raw in raw_models:
        if isinstance(raw, dict):
            model_id = str(raw.get("id") or "").strip()
            if not model_id:
                continue
            efforts = raw.get(
                "reasoning_efforts", raw.get("reasoning_effort")
            )
            models.append(
                {
                    "id": model_id,
                    "context_length": _as_optional_int(raw.get("context_length")),
                    "reasoning_efforts": _as_reasoning_efforts(efforts),
                }
            )
        else:
            model_id = str(raw).strip()
            if not model_id:
                continue
            models.append(
                {
                    "id": model_id,
                    "context_length": None,
                    "reasoning_efforts": group_reasoning_efforts,
                }
            )

    model_ids = [m["id"] for m in models]
    default_model = str(group.get("default_model") or "").strip()
    if not default_model and model_ids:
        default_model = model_ids[0]
    if default_model and default_model not in model_ids:
        models.append(
            {
                "id": default_model,
                "context_length": None,
                "reasoning_efforts": group_reasoning_efforts,
            }
        )

    if group_reasoning_efforts:
        default_entry = next((m for m in models if m["id"] == default_model), None)
        if default_entry is not None and not default_entry["reasoning_efforts"]:
            default_entry["reasoning_efforts"] = group_reasoning_efforts

    return {
        "id": gid,
        "name": str(group.get("name") or ""),
        "base_url": str(group.get("base_url") or ""),
        "api_key": str(group.get("api_key") or ""),
        "models": models,
        "default_model": default_model,
    }


def _legacy_to_group(data: Dict[str, Any]) -> Dict[str, Any]:
    model = str(data.get("model") or "")
    reasoning_efforts = _as_reasoning_efforts(data.get("reasoning_effort"))
    models = (
        [{"id": model, "context_length": None, "reasoning_efforts": reasoning_efforts}]
        if model
        else []
    )
    return {
        "id": "default",
        "name": "默认",
        "base_url": str(data.get("base_url") or ""),
        "api_key": str(data.get("api_key") or ""),
        "models": models,
        "default_model": model,
    }


def _synthesized_config() -> Dict[str, Any]:
    base_url = (os.getenv("LLM_BASE_URL") or _DEFAULTS["base_url"]).rstrip("/")
    api_key = os.getenv("LLM_API_KEY") or _DEFAULTS["api_key"]
    model = os.getenv("LLM_MODEL") or _DEFAULTS["model"]
    reasoning_efforts = _as_reasoning_efforts(
        os.getenv("LLM_REASONING_EFFORT") or _DEFAULTS["reasoning_effort"]
    )
    return {
        "active_group": "default",
        "groups": [
            {
                "id": "default",
                "name": "默认",
                "base_url": base_url,
                "api_key": api_key,
                "models": [
                    {
                        "id": model,
                        "context_length": None,
                        "reasoning_efforts": reasoning_efforts,
                    }
                ],
                "default_model": model,
            }
        ],
    }


def load_config() -> Dict[str, Any]:
    """Return the config as ``{active_group, groups}``.

    A legacy flat config (with ``base_url``/``api_key``/``model`` and no
    ``groups``) is migrated in place to a single ``default`` group; repeated
    loads are idempotent. When nothing is configured, a single default group
    is synthesized from environment variables / built-in defaults.
    """
    data = _load_raw()
    if data is None:
        return _synthesized_config()

    if "groups" not in data and any(
        key in data for key in ("base_url", "api_key", "model")
    ):
        migrated = {"active_group": "default", "groups": [_legacy_to_group(data)]}
        _write(migrated)
        return migrated

    raw_groups = data.get("groups") if isinstance(data.get("groups"), list) else []
    groups = [
        g
        for g in (_normalize_group(raw) for raw in raw_groups)
        if g is not None and g["id"]
    ]
    if not groups:
        return _synthesized_config()

    active_group = str(data.get("active_group") or "")
    if active_group not in {g["id"] for g in groups}:
        active_group = groups[0]["id"]
    return {"active_group": active_group, "groups": groups}


def save_config(data: Dict[str, Any]) -> Dict[str, Any]:
    """Persist the full ``{active_group, groups}`` structure after validation."""
    raw_groups = data.get("groups") if isinstance(data, dict) else None
    if not isinstance(raw_groups, list) or not raw_groups:
        raise ValueError("groups 必须是非空列表")

    groups: List[Dict[str, Any]] = []
    ids: List[str] = []
    for raw in raw_groups:
        group = _normalize_group(raw)
        if group is None or not group["id"]:
            raise ValueError("每个配置组都必须有非空 id")
        if group["id"] in ids:
            raise ValueError("配置组 id 不能重复")
        ids.append(group["id"])
        groups.append(group)

    active_group = str(data.get("active_group") or "")
    if not active_group:
        active_group = groups[0]["id"]
    if active_group not in ids:
        raise ValueError("active_group 必须指向已存在的配置组")

    payload = {"active_group": active_group, "groups": groups}
    _write(payload)
    return payload


def get_effective_config() -> Dict[str, Any]:
    """Resolve the active group into ``{base_url, api_key, model, reasoning_effort, context_length}``.

    ``context_length`` comes from the default model's metadata and is ``None``
    when not configured.
    """
    cfg = load_config()
    groups = cfg.get("groups") or []
    active = cfg.get("active_group") or ""
    group = next((g for g in groups if g["id"] == active), None)
    if group is None:
        group = groups[0] if groups else _synthesized_config()["groups"][0]

    models = group.get("models") or []
    default_model = (
        group.get("default_model")
        or (models[0]["id"] if models else "")
        or os.getenv("LLM_MODEL")
        or _DEFAULTS["model"]
    )
    default_entry = next((m for m in models if m.get("id") == default_model), None)
    efforts = (default_entry or {}).get("reasoning_efforts") or []
    reasoning_effort = efforts[0] if efforts else ""
    return {
        "base_url": (
            group.get("base_url")
            or os.getenv("LLM_BASE_URL")
            or _DEFAULTS["base_url"]
        ).rstrip("/"),
        "api_key": (
            group.get("api_key") or os.getenv("LLM_API_KEY") or _DEFAULTS["api_key"]
        ),
        "model": default_model,
        "reasoning_effort": reasoning_effort,
        "context_length": (default_entry or {}).get("context_length"),
    }


def get_model_context_length(model: Optional[str] = None) -> Optional[int]:
    """Return the configured context window for the given model of the active group.

    Falls back to the group's default model when ``model`` is omitted or
    unknown; returns ``None`` when unconfigured.
    """
    cfg = load_config()
    groups = cfg.get("groups") or []
    active = cfg.get("active_group") or ""
    group = next((g for g in groups if g["id"] == active), None)
    if group is None:
        group = groups[0] if groups else None
    if group is None:
        return None
    models = group.get("models") or []
    target = model or group.get("default_model") or ""
    entry = next(
        (m for m in models if isinstance(m, dict) and m.get("id") == target), None
    )
    if entry is None:
        return None
    value = entry.get("context_length")
    return int(value) if isinstance(value, int) and value > 0 else None
