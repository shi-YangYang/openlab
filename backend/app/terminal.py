"""Async forwarding between a WebSocket and a paramiko interactive shell.

Each WebSocket connection gets its own SSH shell session; the channel and
client are closed once either side ends. Blocking paramiko reads/writes are
wrapped in ``asyncio.to_thread`` so the event loop is never blocked.
"""
import asyncio
import json
from typing import Any, Dict

from . import ssh


async def _send_error(websocket, message: str) -> None:
    try:
        await websocket.send_text(json.dumps({"type": "error", "message": message}))
    except Exception:
        pass


async def ssh_terminal_ws(websocket, server: Dict[str, Any]) -> None:
    client = None
    channel = None
    try:
        try:
            client, channel = await asyncio.to_thread(ssh.open_shell, server)
        except ssh.SSHError as exc:
            await _send_error(websocket, ssh._redact(str(exc), server))
            return
        except Exception as exc:
            await _send_error(websocket, ssh._redact(str(exc), server))
            return

        async def read_loop() -> None:
            while True:
                data = await asyncio.to_thread(channel.recv, 4096)
                if not data:
                    break
                await websocket.send_text(data.decode("utf-8", "replace"))

        async def write_loop() -> None:
            while True:
                text = await websocket.receive_text()
                try:
                    message = json.loads(text)
                except (ValueError, TypeError):
                    message = None
                if isinstance(message, dict) and message.get("type") == "resize":
                    cols = message.get("cols")
                    rows = message.get("rows")
                    if isinstance(cols, int) and isinstance(rows, int):
                        await asyncio.to_thread(
                            channel.resize_pty, width=cols, height=rows
                        )
                else:
                    await asyncio.to_thread(channel.send, text)

        reader = asyncio.create_task(read_loop())
        writer = asyncio.create_task(write_loop())
        done, pending = await asyncio.wait(
            {reader, writer}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            if not task.cancelled():
                task.exception()
    finally:
        if channel is not None:
            try:
                channel.close()
            except Exception:
                pass
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
