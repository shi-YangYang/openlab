"""Server connection persistence.

Server credentials are stored in a local JSON file (default
``backend/data/servers.json``). ``data/`` is gitignored, so credentials never
enter version control; they are also never stored in SQLite, never hardcoded,
and never logged. Read/list responses must be redacted (see :func:`redact`).
"""
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import settings

SERVERS_FILENAME = "servers.json"

_FIELDS = ("name", "host", "port", "username", "auth_type", "password", "private_key")


def _servers_path() -> Path:
    return Path(os.getenv("SERVERS_PATH", str(settings.data_dir / SERVERS_FILENAME)))


def _load() -> List[Dict[str, Any]]:
    path = _servers_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _save(servers: List[Dict[str, Any]]) -> None:
    path = _servers_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(servers, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _clean(data: Dict[str, Any]) -> Dict[str, Any]:
    return {key: data[key] for key in _FIELDS if key in data}


def _normalize_auth(server: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only the credential matching auth_type (drop the other)."""
    if server.get("auth_type") == "key":
        server.pop("password", None)
    else:
        server.pop("private_key", None)
    return server


def list_servers() -> List[Dict[str, Any]]:
    return _load()


def get_server(server_id: str) -> Optional[Dict[str, Any]]:
    for server in _load():
        if server.get("id") == server_id:
            return server
    return None


def add_server(data: Dict[str, Any]) -> Dict[str, Any]:
    server = _clean(data)
    server.setdefault("port", 22)
    server.setdefault("auth_type", "password")
    server["id"] = uuid.uuid4().hex
    _normalize_auth(server)
    servers = _load()
    servers.append(server)
    _save(servers)
    return server


def update_server(server_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    servers = _load()
    for index, server in enumerate(servers):
        if server.get("id") == server_id:
            merged = dict(server)
            merged.update(_clean(data))
            merged["id"] = server_id
            _normalize_auth(merged)
            servers[index] = merged
            _save(servers)
            return merged
    return None


def delete_server(server_id: str) -> bool:
    servers = _load()
    remaining = [s for s in servers if s.get("id") != server_id]
    if len(remaining) == len(servers):
        return False
    _save(remaining)
    return True


def redact(server: Dict[str, Any]) -> Dict[str, Any]:
    """Return a credential-free representation of a server record."""
    return {
        "id": server.get("id", ""),
        "name": server.get("name", ""),
        "host": server.get("host", ""),
        "port": server.get("port", 22),
        "username": server.get("username", ""),
        "auth_type": server.get("auth_type", "password"),
        "has_password": bool(server.get("password")),
        "has_key": bool(server.get("private_key")),
    }
