"""Built-in LLM platform presets.

Each preset maps a human-readable ``name`` to an OpenAI-compatible
``base_url`` and a sensible ``default_model``. The list is intentionally a
plain module-level constant so that adding a new platform is a one-line
change.

All endpoints are OpenAI-compatible (``/chat/completions`` style); LangChain's
``ChatOpenAI`` points at them via ``base_url``.
"""
from typing import Any, Dict, List

LLM_PRESETS: List[Dict[str, Any]] = [
    {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
    },
    {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
    },
    {
        "name": "阿里云百炼 (DashScope)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
    },
    {
        "name": "硅基流动 (SiliconFlow)",
        "base_url": "https://api.siliconflow.cn/v1",
        "default_model": "deepseek-ai/DeepSeek-V3",
    },
    {
        "name": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-plus",
    },
    {
        "name": "Moonshot Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
    },
]
