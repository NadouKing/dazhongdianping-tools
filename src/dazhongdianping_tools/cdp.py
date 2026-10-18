"""Minimal asynchronous CDP transport; only local Chrome endpoints are accepted."""

import asyncio
import contextlib
import json
from urllib.parse import urlsplit

from websockets.asyncio.client import connect

from .errors import DianpingError


def validate_endpoint(url: str) -> None:
    try:
        parsed = urlsplit(url)
        valid = (
            parsed.scheme == "ws"
            and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
            and parsed.port is not None
            and parsed.username is None
            and parsed.password is None
            and parsed.path.startswith("/devtools/browser/")
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        valid = False
    if not valid:
        raise DianpingError("nonlocal_cdp", "CDP 只允许连接本机专用浏览器。")


class CdpConnection:
    def __init__(self, socket, timeout: float):
        self.socket = socket
        self.timeout = timeout
        self._next_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._closed = False
        self._receiver = asyncio.create_task(self._receive())

    @classmethod
    async def open(cls, url: str, request_timeout: float = 30.0):
        validate_endpoint(url)
        try:
            socket = await connect(
                url, open_timeout=min(request_timeout, 10), max_size=16 * 1024 * 1024, proxy=None
            )
        except Exception:
            raise DianpingError("cdp_unavailable", "无法连接本机 Chrome CDP。") from None
        return cls(socket, request_timeout)

    async def _receive(self):
        try:
            async for raw in self.socket:
                message = json.loads(raw)
                pending = self._pending.pop(message.get("id"), None)
                if pending is None or pending.done():
                    continue
                if "error" in message:
                    # Chrome errors can contain page expressions or private URLs.
                    pending.set_exception(DianpingError("cdp_error", "浏览器未能执行 CDP 命令。"))
                else:
                    pending.set_result(message.get("result", {}))
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        finally:
            self._closed = True
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(DianpingError("cdp_closed", "浏览器连接已关闭。"))
            self._pending.clear()

    async def send(self, method: str, params=None, session_id: str | None = None):
        if self._closed:
            raise DianpingError("cdp_closed", "浏览器连接已关闭。")
        self._next_id += 1
        command_id = self._next_id
        message = {"id": command_id, "method": method, "params": params or {}}
        if session_id is not None:
            message["sessionId"] = session_id
        future = asyncio.get_running_loop().create_future()
        self._pending[command_id] = future
        try:
            await self.socket.send(json.dumps(message))
            return await asyncio.wait_for(future, self.timeout)
        except TimeoutError:
            raise DianpingError("cdp_timeout", "等待浏览器 CDP 命令超时。") from None
        except DianpingError:
            raise
        except asyncio.CancelledError:
            raise
        except Exception:
            raise DianpingError("cdp_closed", "浏览器连接已关闭。") from None
        finally:
            self._pending.pop(command_id, None)
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                future.exception()  # Mark a shutdown-time exception as retrieved.

    async def evaluate(self, expression: str, session_id: str):
        result = await self.send(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
            session_id,
        )
        if result.get("exceptionDetails"):
            raise DianpingError("page_evaluation_failed", "页面数据读取失败。")
        return result.get("result", {}).get("value")

    async def close(self):
        if not self._closed:
            await self.socket.close()
        if not self._receiver.done():
            self._receiver.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._receiver
        self._closed = True
