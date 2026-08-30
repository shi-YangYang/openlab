import io
import json
import re

import pytest

from app import config, database, servers, ssh
from app.routes.servers import _resolve_upload_target, _safe_rel_path


def _payload(**overrides):
    payload = {
        "name": "gpu01",
        "host": "10.0.0.1",
        "username": "root",
        "port": 22,
        "auth_type": "password",
        "password": "secret-pw",
    }
    payload.update(overrides)
    return payload


def _create(client, **overrides):
    resp = client.post("/api/servers", json=_payload(**overrides))
    assert resp.status_code == 200
    return resp.json()


def test_server_crud_and_redaction(client):
    created = _create(client)
    assert created["id"]
    assert created["name"] == "gpu01"
    assert created["has_password"] is True
    assert created["has_key"] is False
    assert "password" not in created
    assert "private_key" not in created

    listed = client.get("/api/servers").json()
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]
    assert "password" not in listed[0]
    assert "private_key" not in listed[0]
    assert "secret-pw" not in json.dumps(listed)

    updated = client.put(
        f"/api/servers/{created['id']}",
        json={"name": "gpu02", "port": 2222},
    ).json()
    assert updated["name"] == "gpu02"
    assert updated["port"] == 2222
    assert updated["username"] == "root"

    assert client.delete(f"/api/servers/{created['id']}").status_code == 200
    assert client.get("/api/servers").json() == []


def test_server_not_found(client):
    assert client.get("/api/servers").json() == []
    assert client.put("/api/servers/nope", json={"name": "x"}).status_code == 404
    assert client.delete("/api/servers/nope").status_code == 404
    assert client.post("/api/servers/nope/test").status_code == 404
    assert client.post(
        "/api/servers/nope/monitor"
    ).status_code == 404


def test_server_credentials_stored_in_local_file_not_db(client):
    _create(client)
    path = config.settings.data_dir / "servers.json"
    assert path.exists()
    content = json.loads(path.read_text(encoding="utf-8"))
    assert content[0]["password"] == "secret-pw"
    assert "private_key" not in content[0]

    conn = database._connect()
    try:
        tables = [
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
    finally:
        conn.close()
    assert "servers" not in tables


def test_server_key_auth_drops_password(client):
    created = _create(client, auth_type="key", private_key="KEY")
    assert created["has_key"] is True
    assert created["has_password"] is False
    path = config.settings.data_dir / "servers.json"
    content = json.loads(path.read_text(encoding="utf-8"))
    assert "password" not in content[0]
    assert content[0]["private_key"] == "KEY"


def test_update_preserves_password_when_omitted(client):
    created = _create(client)
    updated = client.put(
        f"/api/servers/{created['id']}", json={"name": "renamed"}
    ).json()
    assert updated["has_password"] is True
    path = config.settings.data_dir / "servers.json"
    content = json.loads(path.read_text(encoding="utf-8"))
    assert content[0]["password"] == "secret-pw"


def test_test_connection_endpoint_mock(client, monkeypatch):
    created = _create(client)
    captured = {}

    def fake_test(server):
        captured["server"] = server
        return {"ok": True, "message": "连接成功", "latency_ms": 12}

    monkeypatch.setattr(ssh, "test_connection", fake_test)

    resp = client.post(f"/api/servers/{created['id']}/test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["latency_ms"] == 12
    assert captured["server"]["password"] == "secret-pw"


def test_deploy_clone_mock(client, monkeypatch):
    created = _create(client)
    captured = {}

    def fake_exec(server, command, timeout=60.0):
        captured["command"] = command
        captured["timeout"] = timeout
        return "Cloning into 'app'..."

    monkeypatch.setattr(ssh, "exec_command", fake_exec)

    resp = client.post(
        f"/api/servers/{created['id']}/deploy/clone",
        json={"repo_url": "https://github.com/org/repo.git", "target_dir": "/home/u/app"},
    )
    assert resp.status_code == 200
    assert resp.json()["output"] == "Cloning into 'app'..."
    assert captured["command"].startswith("git clone ")


def test_deploy_clone_empty_repo_url(client):
    created = _create(client)
    resp = client.post(
        f"/api/servers/{created['id']}/deploy/clone",
        json={"repo_url": "  ", "target_dir": "/tmp/x"},
    )
    assert resp.status_code == 400


def test_deploy_clone_error_returns_502(client, monkeypatch):
    created = _create(client)

    def fail_exec(server, command, timeout=60.0):
        raise ssh.SSHError("connect failed: bad host")

    monkeypatch.setattr(ssh, "exec_command", fail_exec)

    resp = client.post(
        f"/api/servers/{created['id']}/deploy/clone",
        json={"repo_url": "https://x.git", "target_dir": "/tmp/x"},
    )
    assert resp.status_code == 502
    assert "bad host" in resp.json()["detail"]


def test_deploy_upload_mock(client, monkeypatch):
    created = _create(client)
    captured = {}

    def fake_upload(server, local_path, remote_path, timeout=60.0):
        captured["local"] = local_path
        captured["remote"] = remote_path
        return {"message": "上传完成", "files": 5}

    monkeypatch.setattr(ssh, "upload", fake_upload)

    resp = client.post(
        f"/api/servers/{created['id']}/deploy/upload",
        json={"local_path": "C:/code/app", "remote_path": "/home/u/app"},
    )
    assert resp.status_code == 200
    assert resp.json()["files"] == 5
    assert captured["local"] == "C:/code/app"


def test_monitor_structured(client, monkeypatch):
    created = _create(client)
    from app import monitor

    def fake_exec(server, command, timeout=60.0):
        return {
            monitor.GPU_QUERY: "0, NVIDIA A100, 85, 20000, 80000\n",
            monitor.MEMORY_COMMAND: (
                "              total        used        free      shared  buff/cache   available\n"
                "Mem:          32000       12345        1000         100       18655       19000\n"
            ),
            monitor.DISK_COMMAND: (
                "Filesystem      Size  Used Avail Use% Mounted on\n"
                "/dev/sda1       1.0T  500G  400G  56% /\n"
            ),
            monitor.LOAD_COMMAND: "1.20 0.80 0.50 1/123 4567\n",
            monitor.PROCESSES_COMMAND: "USER       PID %CPU %MEM\nroot         1  0.0  0.1\n",
        }[command]

    monkeypatch.setattr(ssh, "exec_command", fake_exec)

    resp = client.post(f"/api/servers/{created['id']}/monitor")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gpu"][0]["name"] == "NVIDIA A100"
    assert data["gpu"][0]["utilization"] == 85
    assert data["memory"] == {"used_mb": 12345, "total_mb": 32000}
    assert data["load"] == [1.2, 0.8, 0.5]
    assert data["disk"][0]["mount"] == "/"
    assert data["raw"] == {}


def test_monitor_fallback_to_raw(client, monkeypatch):
    created = _create(client)
    from app import monitor

    def fake_exec(server, command, timeout=60.0):
        if command == monitor.GPU_QUERY:
            return "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver"
        if command == monitor.GPU_RAW:
            return "no gpu"
        if command == monitor.MEMORY_COMMAND:
            return "free: command not found"
        if command == monitor.DISK_COMMAND:
            return "df: command not found"
        if command == monitor.LOAD_COMMAND:
            return "cat: /proc/loadavg: No such file"
        return "ok"

    monkeypatch.setattr(ssh, "exec_command", fake_exec)

    resp = client.post(f"/api/servers/{created['id']}/monitor")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gpu"] == []
    assert data["raw"]["gpu"] == "no gpu"
    assert data["memory"] is None
    assert "free" in data["raw"]["memory"]
    assert data["load"] == []
    assert "loadavg" in data["raw"]["load"]


def test_exec_endpoint(client, monkeypatch):
    created = _create(client)
    captured = {}

    def fake_exec(server, command, timeout=60.0):
        captured["command"] = command
        return "hello world"

    monkeypatch.setattr(ssh, "exec_command", fake_exec)

    resp = client.post(f"/api/servers/{created['id']}/exec", json={"command": "echo hi"})
    assert resp.status_code == 200
    assert resp.json()["output"] == "hello world"
    assert captured["command"] == "echo hi"


def test_exec_endpoint_empty_command(client):
    created = _create(client)
    resp = client.post(f"/api/servers/{created['id']}/exec", json={"command": "  "})
    assert resp.status_code == 400


def test_exec_endpoint_error_returns_502(client, monkeypatch):
    created = _create(client)

    def fail_exec(server, command, timeout=60.0):
        raise ssh.SSHError("connect failed: bad host")

    monkeypatch.setattr(ssh, "exec_command", fail_exec)
    resp = client.post(f"/api/servers/{created['id']}/exec", json={"command": "ls"})
    assert resp.status_code == 502
    assert "bad host" in resp.json()["detail"]


def test_deploy_upload_multipart(client, monkeypatch):
    created = _create(client)
    captured = {}

    def fake_upload(server, local_path, remote_path, timeout=60.0):
        captured["local"] = local_path
        captured["remote"] = remote_path
        from pathlib import Path

        root = Path(local_path)
        captured["files"] = sorted(
            str(p.relative_to(root)).replace("\\", "/")
            for p in root.rglob("*")
            if p.is_file()
        )
        return {"message": "上传完成", "files": len(captured["files"])}

    monkeypatch.setattr(ssh, "upload", fake_upload)

    resp = client.post(
        f"/api/servers/{created['id']}/deploy/upload",
        data={"remote_path": "/remote/app"},
        files=[
            ("files", ("a.txt", b"content-a")),
            ("files", ("sub/b.txt", b"content-b")),
        ],
    )
    assert resp.status_code == 200
    assert resp.json()["files"] == 2
    assert captured["remote"] == "/remote/app"
    assert captured["files"] == ["a.txt", "sub/b.txt"]


def test_deploy_upload_multipart_missing_remote_path(client):
    created = _create(client)
    resp = client.post(
        f"/api/servers/{created['id']}/deploy/upload",
        data={},
        files=[("files", ("a.txt", b"x"))],
    )
    assert resp.status_code == 400


def test_safe_rel_path_normalizes_malicious_names():
    assert _safe_rel_path("/etc/passwd") == "etc/passwd"
    assert _safe_rel_path("../../evil.txt") == "evil.txt"
    assert _safe_rel_path("C:\\Windows\\x") == "Windows/x"
    assert _safe_rel_path("C:/Windows/x") == "Windows/x"
    assert _safe_rel_path("\\\\host\\share") == "host/share"
    assert _safe_rel_path("//host/share") == "host/share"
    assert _safe_rel_path("a/b.txt") == "a/b.txt"
    assert _safe_rel_path("sub/b.txt") == "sub/b.txt"
    assert _safe_rel_path("") == "upload"
    assert _safe_rel_path("/") == "upload"
    assert _safe_rel_path("C:") == "upload"


def test_resolve_upload_target_rejects_escape(tmp_path):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        _resolve_upload_target(tmp_path, "/etc/passwd")
    assert exc_info.value.status_code == 400


def test_deploy_upload_multipart_malicious_filenames_stay_in_tmpdir(client, monkeypatch):
    created = _create(client)
    captured = {}

    def fake_upload(server, local_path, remote_path, timeout=60.0):
        from pathlib import Path

        root = Path(local_path).resolve()
        captured["root"] = root
        captured["files"] = sorted(
            str(p.relative_to(root)).replace("\\", "/")
            for p in root.rglob("*")
            if p.is_file()
        )
        return {"message": "上传完成", "files": len(captured["files"])}

    monkeypatch.setattr(ssh, "upload", fake_upload)

    resp = client.post(
        f"/api/servers/{created['id']}/deploy/upload",
        data={"remote_path": "/remote/app"},
        files=[
            ("files", ("/etc/passwd", b"a")),
            ("files", ("../../evil.txt", b"b")),
            ("files", ("C:\\Windows\\x", b"c")),
            ("files", ("\\\\host\\share", b"d")),
        ],
    )
    assert resp.status_code == 200
    assert resp.json()["files"] == 4
    files = captured["files"]
    for rel in files:
        parts = rel.split("/")
        assert parts == [p for p in parts if p not in ("", ".", "..")]
        assert not any(re.match(r"^[a-zA-Z]:$", p) for p in parts)
    assert "etc/passwd" in files
    assert "evil.txt" in files


class _FakeChannel:
    def settimeout(self, timeout):
        pass


class _FakeSFTP:
    def __init__(self):
        self.channel = _FakeChannel()
        self.puts = []
        self.mkdirs = []
        self.closed = False

    def get_channel(self):
        return self.channel

    def stat(self, path):
        raise FileNotFoundError(path)

    def mkdir(self, path):
        self.mkdirs.append(path)

    def put(self, local, remote):
        self.puts.append((local, remote))

    def close(self):
        self.closed = True


class _FakeClient:
    def __init__(self, sftp=None, fail_on_connect=None):
        self._sftp = sftp
        self._fail_on_connect = fail_on_connect
        self.connect_kwargs = None
        self.closed = False
        self.commands = []

    def connect(self, **kwargs):
        self.connect_kwargs = kwargs
        if self._fail_on_connect:
            raise self._fail_on_connect

    def open_sftp(self):
        return self._sftp

    def exec_command(self, command, timeout=None):
        self.commands.append(command)
        return None, io.BytesIO(b"out"), io.BytesIO(b"err")

    def close(self):
        self.closed = True


def test_ssh_connect_uses_password(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(ssh, "_build_client", lambda: client)
    ssh.connect({"host": "h", "port": 22, "username": "u", "password": "pw",
                 "auth_type": "password"})
    assert client.connect_kwargs["password"] == "pw"
    assert "pkey" not in client.connect_kwargs


def test_ssh_connect_uses_key(monkeypatch):
    client = _FakeClient()
    sentinel = object()
    monkeypatch.setattr(ssh, "_build_client", lambda: client)
    monkeypatch.setattr(ssh, "_load_private_key", lambda key: sentinel)
    ssh.connect({"host": "h", "port": 22, "username": "u", "auth_type": "key",
                 "private_key": "KEY"})
    assert client.connect_kwargs["pkey"] is sentinel
    assert "password" not in client.connect_kwargs


def test_ssh_connect_failure_redacts_password(monkeypatch):
    client = _FakeClient(fail_on_connect=Exception("auth failed with secret-pw"))
    monkeypatch.setattr(ssh, "_build_client", lambda: client)
    with pytest.raises(ssh.SSHError) as exc_info:
        ssh.connect({"host": "h", "port": 22, "username": "u",
                     "password": "secret-pw"})
    assert "secret-pw" not in str(exc_info.value)


def test_ssh_exec_command_combines_output(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(ssh, "_build_client", lambda: client)
    out = ssh.exec_command({"host": "h"}, "echo hi")
    assert out == "out\nerr"


def test_ssh_test_connection_ok(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(ssh, "_build_client", lambda: client)
    result = ssh.test_connection({"host": "h"})
    assert result["ok"] is True
    assert result["latency_ms"] >= 0


def test_ssh_test_connection_failure(monkeypatch):
    def fail(server, timeout=10.0):
        raise ssh.SSHError("timeout")

    monkeypatch.setattr(ssh, "connect", fail)
    result = ssh.test_connection({"host": "h"})
    assert result["ok"] is False
    assert result["message"] == "timeout"
    assert result["latency_ms"] is None


def test_ssh_upload_missing_local_path(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(ssh, "_build_client", lambda: client)
    with pytest.raises(ssh.SSHError):
        ssh.upload({"host": "h"}, "/no/such/dir", "/remote")


def test_ssh_upload_directory_recursive(tmp_path, monkeypatch):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "sub" / "b.txt").write_text("b", encoding="utf-8")

    sftp = _FakeSFTP()
    client = _FakeClient(sftp=sftp)
    monkeypatch.setattr(ssh, "_build_client", lambda: client)

    result = ssh.upload({"host": "h"}, str(tmp_path), "/remote/app")
    assert result["files"] == 2
    assert len(sftp.puts) == 2
    assert client.closed is True
