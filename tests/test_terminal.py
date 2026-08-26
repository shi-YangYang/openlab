import asyncio
import json
import threading

from starlette.websockets import WebSocketDisconnect

from app import ssh, terminal


class FakeChannel:
    def __init__(self, outgoing=None, block=False):
        self.outgoing = list(outgoing or [])
        self.block = block
        self.unblock = threading.Event()
        self.sent = []
        self.resizes = []
        self.closed = False

    def recv(self, nbytes):
        if self.outgoing:
            return self.outgoing.pop(0)
        if self.block:
            self.unblock.wait(timeout=10)
        return b""

    def send(self, data):
        self.sent.append(data)

    def resize_pty(self, width=None, height=None):
        self.resizes.append((width, height))

    def close(self):
        self.closed = True
        self.unblock.set()


class FakeClient:
    def __init__(self, channel):
        self.channel = channel
        self.closed = False

    def invoke_shell(self, term="xterm-256color", width=80, height=24):
        self.invoke_kwargs = {"term": term, "width": width, "height": height}
        return self.channel

    def close(self):
        self.closed = True


class FakeWebSocket:
    def __init__(self, incoming=None, disconnect=True):
        self.incoming = list(incoming or [])
        self.disconnect = disconnect
        self.sent = []
        self.closed = False

    async def send_text(self, text):
        self.sent.append(text)

    async def receive_text(self):
        if self.incoming:
            return self.incoming.pop(0)
        if self.disconnect:
            raise WebSocketDisconnect(code=1000)
        await asyncio.Event().wait()
        raise WebSocketDisconnect(code=1000)

    async def close(self, code=1000):
        self.closed = True


def _server(**overrides):
    server = {"host": "h", "username": "u", "password": "secret-pw"}
    server.update(overrides)
    return server


def test_terminal_output_forwarding(monkeypatch):
    channel = FakeChannel(outgoing=[b"hello", b" world"])
    client = FakeClient(channel)
    monkeypatch.setattr(ssh, "open_shell", lambda server: (client, channel))

    ws = FakeWebSocket(disconnect=False)
    asyncio.run(terminal.ssh_terminal_ws(ws, _server()))

    assert ws.sent == ["hello", " world"]
    assert channel.closed is True
    assert client.closed is True


def test_terminal_resize_and_input_forwarding(monkeypatch):
    channel = FakeChannel(block=True)
    client = FakeClient(channel)
    monkeypatch.setattr(ssh, "open_shell", lambda server: (client, channel))

    ws = FakeWebSocket(
        incoming=[
            json.dumps({"type": "resize", "cols": 120, "rows": 40}),
            "ls -la\r",
        ]
    )
    asyncio.run(terminal.ssh_terminal_ws(ws, _server()))

    assert channel.resizes == [(120, 40)]
    assert channel.sent == ["ls -la\r"]
    assert channel.closed is True
    assert client.closed is True


def test_terminal_ignores_invalid_resize(monkeypatch):
    channel = FakeChannel(block=True)
    client = FakeClient(channel)
    monkeypatch.setattr(ssh, "open_shell", lambda server: (client, channel))

    ws = FakeWebSocket(incoming=[json.dumps({"type": "resize", "cols": "x", "rows": "y"})])
    asyncio.run(terminal.ssh_terminal_ws(ws, _server()))

    assert channel.resizes == []
    assert channel.sent == []


def test_terminal_connect_error_redacted(monkeypatch):
    def fail_open_shell(server):
        raise ssh.SSHError("auth failed with secret-pw")

    monkeypatch.setattr(ssh, "open_shell", fail_open_shell)

    ws = FakeWebSocket()
    asyncio.run(terminal.ssh_terminal_ws(ws, _server()))

    assert len(ws.sent) == 1
    message = json.loads(ws.sent[0])
    assert message["type"] == "error"
    assert "secret-pw" not in message["message"]


def test_terminal_connect_unexpected_error_redacted(monkeypatch):
    def fail_open_shell(server):
        raise RuntimeError("boom secret-pw")

    monkeypatch.setattr(ssh, "open_shell", fail_open_shell)

    ws = FakeWebSocket()
    asyncio.run(terminal.ssh_terminal_ws(ws, _server()))

    assert len(ws.sent) == 1
    message = json.loads(ws.sent[0])
    assert message["type"] == "error"
    assert "secret-pw" not in message["message"]


def test_terminal_disconnect_releases_resources(monkeypatch):
    channel = FakeChannel(block=True)
    client = FakeClient(channel)
    monkeypatch.setattr(ssh, "open_shell", lambda server: (client, channel))

    ws = FakeWebSocket(incoming=["exit\r"])
    asyncio.run(terminal.ssh_terminal_ws(ws, _server()))

    assert channel.closed is True
    assert client.closed is True


def test_terminal_ws_server_not_found(client):
    with client.websocket_connect("/api/servers/nope/terminal") as ws:
        data = ws.receive_json()
        assert data["type"] == "error"
        assert "nope" in data["message"]


def test_terminal_ws_passes_raw_credentials(client, monkeypatch):
    created = client.post(
        "/api/servers",
        json={
            "name": "gpu01",
            "host": "10.0.0.1",
            "username": "root",
            "port": 22,
            "auth_type": "password",
            "password": "secret-pw",
        },
    ).json()

    captured = {}

    async def fake_ssh_terminal_ws(websocket, server):
        captured["server"] = server
        await websocket.send_text("ok")

    monkeypatch.setattr(terminal, "ssh_terminal_ws", fake_ssh_terminal_ws)

    with client.websocket_connect(f"/api/servers/{created['id']}/terminal") as ws:
        assert ws.receive_text() == "ok"

    assert captured["server"]["password"] == "secret-pw"
