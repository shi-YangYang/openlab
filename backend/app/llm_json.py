"""Shared tolerant JSON parser for LLM responses (spec-035 FR-3).

Every LLM-facing module used to re-implement the same three-layer tolerance:
strip markdown code fences → try a direct ``json.loads`` → slice the outermost
``{...}``/``[...]`` block out of surrounding noise and retry. This module is
the single implementation; call sites keep their own retry loops.
"""
import json
from typing import Any, Optional, Type

from pydantic import BaseModel


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.lstrip("json").strip()
    return text


def _slice_between(text: str, opener: str, closer: str) -> Optional[str]:
    start = text.find(opener)
    end = text.rfind(closer)
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return None


def parse_llm_json(
    text: str,
    model_cls: Optional[Type[BaseModel]] = None,
    container: Optional[str] = None,
) -> Any:
    """Parse an LLM response into JSON, tolerating code fences and noise.

    Layers, in order:

    1. strip markdown code fences;
    2. direct ``json.loads``;
    3. on failure, slice the outermost ``{...}`` (``container="object"``),
       ``[...]`` (``container="array"``) or either (``container=None``) block
       out of surrounding noise and parse again.

    With ``model_cls`` the parsed value is validated via
    ``model_cls.model_validate``. Any failing layer raises ``ValueError``
    carrying the stage information. ``container="array"`` wraps a bare JSON
    object into a one-item list (historical behaviour of the innovation /
    experiment parsers); ``container="object"`` rejects non-dict payloads.
    """
    if container not in (None, "object", "array"):
        raise ValueError(f"未知的 container 参数: {container}")
    text = _strip_fences(text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
        candidates = []
        if container in (None, "object"):
            sliced = _slice_between(text, "{", "}")
            if sliced is not None:
                candidates.append(sliced)
        if container in (None, "array"):
            sliced = _slice_between(text, "[", "]")
            if sliced is not None:
                candidates.append(sliced)
        for candidate in candidates:
            try:
                data = json.loads(candidate)
                break
            except json.JSONDecodeError:
                continue
        if data is None:
            raise ValueError("LLM 返回内容不是合法 JSON（直接解析与截取均失败）")
    if container == "object" and not isinstance(data, dict):
        raise ValueError("LLM 返回内容不是 JSON 对象")
    if container == "array":
        if isinstance(data, dict):
            data = [data]
        elif not isinstance(data, list):
            raise ValueError("LLM 返回内容不是 JSON 数组")
    if model_cls is not None:
        try:
            return model_cls.model_validate(data)
        except Exception as exc:  # noqa: BLE001 - surface as ValueError w/ stage
            raise ValueError(f"LLM 返回 JSON 未通过 {model_cls.__name__} 校验: {exc}")
    return data
