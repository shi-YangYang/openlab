from app import config


def _create_session(client):
    resp = client.post("/api/agent/sessions", json={})
    assert resp.status_code == 200
    return resp.json()


def test_upload_attachment(client):
    created = _create_session(client)
    sid = created["id"]

    content = b"print('hi')"
    resp = client.post(
        f"/api/agent/sessions/{sid}/attachments",
        files={"file": ("notes.py", content)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["path"] == "notes.py"
    assert body["size"] == len(content)

    target = config.settings.data_dir / "sandbox" / sid / "notes.py"
    assert target.is_file()
    assert target.read_bytes() == content

    # 同名文件直接覆盖（沙箱内幂等）
    resp = client.post(
        f"/api/agent/sessions/{sid}/attachments",
        files={"file": ("notes.py", b"updated")},
    )
    assert resp.status_code == 200
    assert target.read_bytes() == b"updated"


def test_upload_folder_hierarchy(client):
    created = _create_session(client)
    sid = created["id"]

    resp = client.post(
        f"/api/agent/sessions/{sid}/attachments",
        files={"file": ("a.txt", b"data")},
        data={"path": "sub/dir/a.txt"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"path": "sub/dir/a.txt", "size": 4}

    target = config.settings.data_dir / "sandbox" / sid / "sub" / "dir" / "a.txt"
    assert target.is_file()
    assert target.read_bytes() == b"data"


def test_upload_path_traversal_sanitized(client):
    created = _create_session(client)
    sid = created["id"]

    resp = client.post(
        f"/api/agent/sessions/{sid}/attachments",
        files={"file": ("passwd", b"root")},
        data={"path": "../../etc/passwd"},
    )
    assert resp.status_code == 200
    rel = resp.json()["path"]

    sandbox_root = (config.settings.data_dir / "sandbox" / sid).resolve()
    target = (sandbox_root / rel).resolve()
    assert target.is_relative_to(sandbox_root)
    assert target.is_file()
    assert target.read_bytes() == b"root"


def test_upload_missing_session_returns_404(client):
    resp = client.post(
        "/api/agent/sessions/does-not-exist/attachments",
        files={"file": ("a.txt", b"x")},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "会话不存在"
