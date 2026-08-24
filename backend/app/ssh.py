"""SSH helpers built on paramiko.

All operations carry a timeout and catch exceptions, returning friendly
messages that never include the server password or private key.
"""
import io
import posixpath
import time
from pathlib import Path
from typing import Any, Dict, List

import paramiko


class SSHError(Exception):
    """Raised for SSH connection/command errors, with a safe message."""


def _secrets(server: Dict[str, Any]) -> List[str]:
    password = server.get("password")
    return [str(password)] if password else []


def _redact(text: str, server: Dict[str, Any]) -> str:
    if not text:
        return text
    for secret in _secrets(server):
        if secret in text:
            text = text.replace(secret, "***")
    return text


def _load_private_key(private_key: str):
    for cls in (paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey):
        try:
            return cls.from_private_key(io.StringIO(private_key))
        except Exception:
            continue
    raise ValueError("无法解析私钥，仅支持 RSA / Ed25519 / ECDSA")


def _build_client() -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    return client


def connect(server: Dict[str, Any], timeout: float = 10.0) -> paramiko.SSHClient:
    client = _build_client()
    kwargs: Dict[str, Any] = {
        "hostname": server.get("host"),
        "port": int(server.get("port") or 22),
        "username": server.get("username"),
        "timeout": timeout,
    }
    try:
        if server.get("auth_type") == "key":
            private_key = server.get("private_key")
            if not private_key:
                raise ValueError("认证方式为密钥，但未提供私钥")
            kwargs["pkey"] = _load_private_key(private_key)
        else:
            kwargs["password"] = server.get("password") or ""
        client.connect(**kwargs)
    except Exception as exc:
        try:
            client.close()
        except Exception:
            pass
        raise SSHError(_redact(str(exc), server)) from exc
    return client


def test_connection(server: Dict[str, Any], timeout: float = 10.0) -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        client = connect(server, timeout)
    except SSHError as exc:
        return {"ok": False, "message": str(exc), "latency_ms": None}
    try:
        client.close()
    except Exception:
        pass
    return {
        "ok": True,
        "message": "连接成功",
        "latency_ms": int((time.perf_counter() - start) * 1000),
    }


def exec_command(
    server: Dict[str, Any], command: str, timeout: float = 60.0
) -> str:
    """Run a command and return combined stdout/stderr (raw)."""
    client = connect(server, timeout)
    try:
        _stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        return (out + ("\n" + err if err else "")).strip()
    except Exception as exc:
        raise SSHError(_redact(str(exc), server)) from exc
    finally:
        try:
            client.close()
        except Exception:
            pass


def _mkdir_p(sftp, remote_dir: str) -> None:
    if remote_dir in ("", "/", "."):
        return
    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        parent = posixpath.dirname(remote_dir)
        if parent and parent != remote_dir:
            _mkdir_p(sftp, parent)
        try:
            sftp.mkdir(remote_dir)
        except OSError:
            pass


def upload(
    server: Dict[str, Any],
    local_path: str,
    remote_path: str,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    """Recursively upload a local file/directory to the remote server."""
    local = Path(local_path)
    if not local.exists():
        raise SSHError(f"本地路径不存在: {local_path}")

    client = connect(server, timeout)
    count = 0
    try:
        sftp = client.open_sftp()
        try:
            sftp.get_channel().settimeout(timeout)
            if local.is_dir():
                _mkdir_p(sftp, remote_path)
                for item in sorted(local.rglob("*")):
                    rel = item.relative_to(local)
                    target = posixpath.join(remote_path, rel.as_posix())
                    if item.is_dir():
                        _mkdir_p(sftp, target)
                    else:
                        _mkdir_p(sftp, posixpath.dirname(target))
                        sftp.put(str(item), target)
                        count += 1
            else:
                target = (
                    posixpath.join(remote_path, local.name)
                    if remote_path.endswith("/")
                    else remote_path
                )
                _mkdir_p(sftp, posixpath.dirname(target))
                sftp.put(str(local), target)
                count += 1
        finally:
            sftp.close()
    except SSHError:
        raise
    except Exception as exc:
        raise SSHError(_redact(str(exc), server)) from exc
    finally:
        try:
            client.close()
        except Exception:
            pass
    return {"message": "上传完成", "files": count}
