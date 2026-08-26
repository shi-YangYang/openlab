"""Platform login-state management (spec-014)."""
from .sessions import (
    EXPIRED,
    LOGGED_IN,
    LOGGING_IN,
    NOT_LOGGED_IN,
    SUPPORTED_PLATFORMS,
    LoginExpiredError,
    LoginRequiredError,
    delete_state,
    get_state,
    has_state,
    list_states,
    load_state,
    reset_states,
    save_state,
    set_state,
)
from . import browser, sessions

__all__ = [
    "EXPIRED",
    "LOGGED_IN",
    "LOGGING_IN",
    "NOT_LOGGED_IN",
    "SUPPORTED_PLATFORMS",
    "LoginExpiredError",
    "LoginRequiredError",
    "browser",
    "sessions",
    "delete_state",
    "get_state",
    "has_state",
    "list_states",
    "load_state",
    "reset_states",
    "save_state",
    "set_state",
]
