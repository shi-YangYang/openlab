"""Built-in reasoning-effort dictionary.

Reasoning-effort values are provider-specific: OpenAI uses ``low/medium/high``,
while others (DeepSeek, Qwen, GLM, Gemini, Claude, Grok, Kimi...) use additional
vocabularies such as ``minimal``/``max``/``xhigh``. The standard
OpenAI-compatible ``/models`` endpoint returns only model ids, so these values
cannot be obtained from the API. This module ships a small curated mapping
(derived from OpenRouter's per-model ``reasoning.supported_efforts`` metadata)
keyed by model-name pattern. :func:`guess_reasoning_efforts` returns a
best-effort default that the user can always override in settings.
"""
import re
from typing import List

# Ordered (pattern, efforts) pairs; the first matching pattern wins.
_PATTERNS: List = [
    (re.compile(r"(^|[-/.])o[0-9]+(\b|[-/.])", re.IGNORECASE), ["low", "medium", "high"]),
    (re.compile(r"gpt[-_.]?5", re.IGNORECASE), ["minimal", "low", "medium", "high"]),
    (re.compile(r"deepseek.*(reasoner|r1)", re.IGNORECASE), ["low", "medium", "high"]),
    (re.compile(r"deepseek", re.IGNORECASE), ["low", "high", "max", "xhigh"]),
    (re.compile(r"qwen", re.IGNORECASE), ["minimal", "low", "medium", "high", "xhigh"]),
    (re.compile(r"\bglm", re.IGNORECASE), ["low", "high", "max", "xhigh"]),
    (re.compile(r"gemini", re.IGNORECASE), ["minimal", "low", "medium", "high"]),
    (re.compile(r"claude", re.IGNORECASE), ["low", "medium", "high", "max", "xhigh"]),
    (re.compile(r"grok", re.IGNORECASE), ["low", "medium", "high", "xhigh"]),
    (re.compile(r"(kimi|moonshot)", re.IGNORECASE), ["low", "medium", "high", "max"]),
]


def guess_reasoning_efforts(model_id: str) -> List[str]:
    """Return a best-effort list of reasoning-effort values for a model id."""
    for pattern, efforts in _PATTERNS:
        if pattern.search(model_id):
            return list(efforts)
    return []
