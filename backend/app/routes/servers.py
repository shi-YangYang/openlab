"""Server routes: CRUD, connection test, deploy, exec, monitor, terminal."""
import json
import re
import shlex
import shutil
import tempfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Request, WebSocket

from .. import monitor, servers, ssh, terminal
from ..schemas import (
    CloneRequest,
    CloneResponse,
    ExecRequest,
    ExecResponse,
    MonitorResponse,
    ServerInput,
    ServerOutput,
    ServerUpdate,
    TestConnectionResponse,
    UploadResponse,
)

router = APIRouter()


def _require_server(server_id: str) -> dict:
    server = servers.get_server(server_id)
    if server is None:
        raise HTTPException(status_code=404, detail=f"Server not found: {server_id}")
    return server


@router.get("", response_model=List[ServerOutput])
async def list_servers() -> List[dict]:
    return [servers.redact(s) for s in servers.list_servers()]


@router.post("", response_model=ServerOutput)
async def create_server(req: ServerInput) -> dict:
    return servers.redact(servers.add_server(req.model_dump()))


@router.post("/{server_id}/test", response_model=TestConnectionResponse)
async def test_server(server_id: str) -> dict:
    server = _require_server(server_id)
    return ssh.test_connection(server)


@router.post("/{server_id}/deploy/clone", response_model=CloneResponse)
async def deploy_clone(server_id: str, req: CloneRequest) -> dict:
    server = _require_server(server_id)
    if not req.repo_url.strip():
        raise HTTPException(status_code=400, detail="repo_url must not be empty")
    command = f"git clone {shlex.quote(req.repo_url)} {shlex.quote(req.target_dir)}"
    try:
        output = ssh.exec_command(server, command)
    except ssh.SSHError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"output": output}


@router.post("/{server_id}/deploy/upload", response_model=UploadResponse)
async def deploy_upload(server_id: str, request: Request) -> dict:
    server = _require_server(server_id)
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        return await _deploy_upload_files(server, request)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求体必须是 JSON 或 multipart 表单")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="请求体必须是 JSON 对象")
    local_path = (body.get("local_path") or "").strip()
    remote_path = (body.get("remote_path") or "").strip()
    if not local_path:
        raise HTTPException(status_code=400, detail="local_path must not be empty")
    try:
        return ssh.upload(server, local_path, remote_path)
    except ssh.SSHError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/{server_id}/exec", response_model=ExecResponse)
async def exec_server(server_id: str, req: ExecRequest) -> dict:
    server = _require_server(server_id)
    if not req.command.strip():
        raise HTTPException(status_code=400, detail="command must not be empty")
    try:
        output = ssh.exec_command(server, req.command)
    except ssh.SSHError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"output": output}


@router.post("/{server_id}/monitor", response_model=MonitorResponse)
async def monitor_server(server_id: str) -> dict:
    server = _require_server(server_id)
    return monitor.collect(server)


@router.put("/{server_id}", response_model=ServerOutput)
async def update_server(server_id: str, req: ServerUpdate) -> dict:
    updated = servers.update_server(server_id, req.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Server not found: {server_id}")
    return servers.redact(updated)


@router.delete("/{server_id}")
async def delete_server(server_id: str) -> dict:
    if not servers.delete_server(server_id):
        raise HTTPException(status_code=404, detail=f"Server not found: {server_id}")
    return {"status": "ok"}


@router.websocket("/{server_id}/terminal")
async def server_terminal_ws(websocket: WebSocket, server_id: str) -> None:
    await websocket.accept()
    try:
        server = _require_server(server_id)
    except HTTPException as exc:
        await websocket.send_text(
            json.dumps({"type": "error", "message": str(exc.detail)})
        )
        await websocket.close()
        return
    await terminal.ssh_terminal_ws(websocket, server)


_DRIVE_PREFIX_RE = re.compile(r"^[a-zA-Z]:$")


def _safe_rel_path(name: str) -> str:
    parts = [
        part
        for part in name.replace("\\", "/").split("/")
        if part not in ("", ".", "..") and not _DRIVE_PREFIX_RE.match(part)
    ]
    return "/".join(parts) if parts else "upload"


def _resolve_upload_target(tmpdir: Path, rel: str) -> Path:
    root = tmpdir.resolve()
    target = (tmpdir / rel).resolve()
    if not target.is_relative_to(root):
        raise HTTPException(status_code=400, detail=f"非法文件名: {rel}")
    return target


async def _deploy_upload_files(server: dict, request: Request) -> dict:
    form = await request.form()
    remote_path = str(form.get("remote_path") or "").strip()
    files = form.getlist("files")
    if not remote_path:
        raise HTTPException(status_code=400, detail="remote_path must not be empty")
    if not files:
        raise HTTPException(status_code=400, detail="未选择任何文件")
    tmpdir = Path(tempfile.mkdtemp(prefix="openlab-upload-"))
    try:
        for item in files:
            if not hasattr(item, "read"):
                continue
            rel = _safe_rel_path(getattr(item, "filename", "") or "upload")
            target = _resolve_upload_target(tmpdir, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(await item.read())
        try:
            return ssh.upload(server, str(tmpdir), remote_path)
        except ssh.SSHError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
