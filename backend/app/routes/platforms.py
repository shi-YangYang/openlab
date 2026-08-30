"""Platform login-state routes."""
import threading
from typing import List

from fastapi import APIRouter, HTTPException

from ..platforms import browser, sessions
from ..schemas import PlatformStatus

router = APIRouter()


def _require_platform(platform: str) -> None:
    if platform not in sessions.SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=404, detail=f"Unknown platform: {platform}")


@router.get("", response_model=List[PlatformStatus])
async def list_platforms() -> List[dict]:
    return sessions.list_states()


@router.get("/{platform}/status", response_model=PlatformStatus)
async def get_platform_status(platform: str) -> dict:
    _require_platform(platform)
    return {"platform": platform, "state": sessions.get_state(platform)}


@router.post("/{platform}/login", response_model=PlatformStatus)
async def login_platform(platform: str) -> dict:
    _require_platform(platform)
    if sessions.get_state(platform) == sessions.LOGGING_IN:
        return {"platform": platform, "state": sessions.LOGGING_IN}
    sessions.set_state(platform, sessions.LOGGING_IN)
    threading.Thread(target=browser.run_login, args=(platform,), daemon=True).start()
    return {"platform": platform, "state": sessions.LOGGING_IN}


@router.post("/{platform}/logout", response_model=PlatformStatus)
async def logout_platform(platform: str) -> dict:
    _require_platform(platform)
    sessions.delete_state(platform)
    sessions.set_state(platform, sessions.NOT_LOGGED_IN)
    return {"platform": platform, "state": sessions.NOT_LOGGED_IN}


@router.post("/{platform}/login/complete", response_model=PlatformStatus)
async def complete_platform_login(platform: str) -> dict:
    _require_platform(platform)
    browser.complete_login(platform)
    return {"platform": platform, "state": sessions.get_state(platform)}


@router.post("/{platform}/login/cancel", response_model=PlatformStatus)
async def cancel_platform_login(platform: str) -> dict:
    _require_platform(platform)
    browser.cancel_login(platform)
    return {"platform": platform, "state": sessions.get_state(platform)}
