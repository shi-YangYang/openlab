"""Secret scrubbing shared by the agent loop, exports and the experiment runner.

Scrub the LLM API key and any server passwords from a string (NFR-2).
Secrets shorter than ``_MIN_SECRET_LENGTH`` are ignored to avoid
over-redacting common single characters.
"""
from typing import List

from .llm_config import get_effective_config
from . import servers

_MIN_SECRET_LENGTH = 4


def redact_secrets(text: str) -> str:
    secrets: List[str] = []
    try:
        api_key = get_effective_config().get("api_key") or ""
    except Exception:
        api_key = ""
    if api_key:
        secrets.append(api_key)
    try:
        for server in servers.list_servers():
            password = server.get("password")
            if password:
                secrets.append(str(password))
    except Exception:
        pass
    for secret in secrets:
        if secret and len(secret) >= _MIN_SECRET_LENGTH and secret in text:
            text = text.replace(secret, "***")
    return text
