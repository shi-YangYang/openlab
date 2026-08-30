"""LLM routes: presets, config, connection test, and model listing."""
import time
from typing import Any, List, Optional

import httpx
from fastapi import APIRouter, HTTPException

from ..llm_config import load_config, save_config
from ..presets import LLM_PRESETS
from ..reasoning_efforts import guess_reasoning_efforts
from ..schemas import (
    LLMConfigResponse,
    LLMModelsRequest,
    LLMModelsResponse,
    LLMPreset,
    LLMTestRequest,
    LLMTestResponse,
)

router = APIRouter()


def _redact(text: str, secret: str) -> str:
    if secret and secret in text:
        return text.replace(secret, "***")
    return text


def _extract_error_body(resp: httpx.Response) -> str:
    try:
        data = resp.json()
    except ValueError:
        return (resp.text or "").strip()[:200]
    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or error)[:200]
    if isinstance(error, str):
        return error[:200]
    return (resp.text or "").strip()[:200]


@router.get("/presets", response_model=List[LLMPreset])
async def llm_presets() -> List[dict]:
    return LLM_PRESETS


@router.get("/config", response_model=LLMConfigResponse)
async def get_llm_config() -> dict:
    return load_config()


@router.post("/test", response_model=LLMTestResponse)
async def test_llm_connection(req: LLMTestRequest) -> dict:
    base_url = (req.base_url or "").strip()
    api_key = (req.api_key or "").strip()
    model = (req.model or "").strip()

    if not base_url or not api_key or not model:
        return LLMTestResponse(ok=False, message="请先填写完整配置")

    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }
    headers = {"Authorization": f"Bearer {api_key}"}

    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
        latency_ms = int((time.perf_counter() - start) * 1000)
    except httpx.TimeoutException:
        return LLMTestResponse(ok=False, message="请求超时（15 秒）")
    except httpx.HTTPError as exc:
        message = _redact(str(exc), api_key)
        return LLMTestResponse(ok=False, message=f"请求失败：{message}")
    except Exception as exc:
        message = _redact(str(exc), api_key)
        return LLMTestResponse(ok=False, message=f"请求失败：{message}")

    if resp.status_code >= 400:
        detail = _redact(_extract_error_body(resp), api_key)
        return LLMTestResponse(
            ok=False,
            message=f"HTTP {resp.status_code}: {detail}" if detail else f"HTTP {resp.status_code}",
            latency_ms=latency_ms,
        )

    try:
        summary = _extract_content_summary(resp.json())
    except ValueError:
        summary = "连接成功"
    return LLMTestResponse(ok=True, message=summary, latency_ms=latency_ms)


@router.post("/models", response_model=LLMModelsResponse)
async def llm_models(req: LLMModelsRequest) -> dict:
    base_url = (req.base_url or "").strip()
    api_key = (req.api_key or "").strip()

    if not base_url:
        raise HTTPException(status_code=400, detail="请先填写 Base URL")

    url = f"{base_url.rstrip('/')}/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
    except httpx.TimeoutException:
        raise HTTPException(status_code=502, detail="获取模型列表超时（15 秒）")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=_redact(str(exc), api_key))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=_redact(str(exc), api_key))

    if resp.status_code >= 400:
        detail = _redact(_extract_error_body(resp), api_key)
        raise HTTPException(
            status_code=resp.status_code,
            detail=detail or f"HTTP {resp.status_code}",
        )

    try:
        data = resp.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="返回内容不是有效 JSON")

    items = data.get("data") if isinstance(data, dict) else None
    models: List[dict] = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                efforts = _extract_reasoning_efforts(item) or guess_reasoning_efforts(item["id"])
                models.append(
                    {
                        "id": item["id"],
                        "context_length": _extract_context_length(item),
                        "reasoning_efforts": efforts,
                    }
                )
            elif isinstance(item, str):
                models.append(
                    {
                        "id": item,
                        "context_length": None,
                        "reasoning_efforts": guess_reasoning_efforts(item),
                    }
                )
    return {"models": models}


@router.put("/config", response_model=LLMConfigResponse)
async def update_llm_config(req: LLMConfigResponse) -> dict:
    try:
        return save_config(req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _extract_content_summary(data: Any) -> str:
    try:
        choices = data.get("choices") if isinstance(data, dict) else None
        content = choices[0].get("message", {}).get("content", "")
    except (IndexError, AttributeError, TypeError):
        content = ""
    if isinstance(content, str) and content.strip():
        return content.strip()[:200]
    return "连接成功"


_CONTEXT_LENGTH_KEYS = (
    "max_context_length",
    "context_length",
    "context_window",
    "context_window_tokens",
    "max_context_tokens",
    "contextwindow",
    "max_tokens",
)


def _to_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(float(text))
        except ValueError:
            return None
    return None


def _find_key(node: Any, target: str) -> Optional[Any]:
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str) and key.lower() == target:
                return value
        for value in node.values():
            found = _find_key(value, target)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_key(value, target)
            if found is not None:
                return found
    return None


def _extract_context_length(item: Any) -> Optional[int]:
    if not isinstance(item, dict):
        return None
    for key in _CONTEXT_LENGTH_KEYS:
        value = _find_key(item, key)
        parsed = _to_int(value)
        if parsed is not None:
            return parsed
    return None


_REASONING_EFFORT_KEYS = (
    "reasoning_efforts",
    "supported_reasoning_efforts",
    "reasoning_effort_options",
    "reasoning_effort",
)


def _as_string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        result: List[str] = []
        for item in value:
            text = str(item).strip()
            if text and text not in result:
                result.append(text)
        return result
    text = str(value).strip()
    if not text:
        return []
    parts = [p.strip() for p in text.split(",") if p.strip()]
    return parts if parts else [text]


def _extract_reasoning_efforts(item: Any) -> List[str]:
    if not isinstance(item, dict):
        return []
    for key in _REASONING_EFFORT_KEYS:
        value = _find_key(item, key)
        result = _as_string_list(value)
        if result:
            return result
    return []
