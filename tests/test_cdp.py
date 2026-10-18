import asyncio
import json

import pytest

from dazhongdianping_tools.cdp import CdpConnection, validate_endpoint
from dazhongdianping_tools.errors import DianpingError


@pytest.mark.parametrize(
    "url",
    [
        "ws://example.com/devtools/browser/id",
        "wss://127.0.0.1/devtools/browser/id",
        "ws://user:private@127.0.0.1:9222/devtools/browser/id",
        "ws://127.0.0.1:9222/devtools/browser/id?token=private",
    ],
)
def test_only_local_browser_debugger_endpoint_allowed(url):
    with pytest.raises(DianpingError) as error:
        validate_endpoint(url)
    assert error.value.code == "nonlocal_cdp"
    assert "private" not in str(error.value)


class FakeSocket:
    def __init__(self, mode="reply"):
        self.queue = asyncio.Queue()
        self.mode = mode

    def __aiter__(self):
        return self

    async def __anext__(self):
        value = await self.queue.get()
        if value is None:
            raise StopAsyncIteration
        return value

    async def send(self, raw):
        command = json.loads(raw)
        if self.mode == "reply":
            await self.queue.put(
                json.dumps({"id": command["id"], "result": {"method": command["method"]}})
            )
        elif self.mode == "error":
            await self.queue.put(
                json.dumps({"id": command["id"], "error": {"message": "private-cookie-secret"}})
            )

    async def close(self):
        await self.queue.put(None)


def test_cdp_correlates_concurrent_commands_and_closes_idempotently():
    async def run():
        connection = CdpConnection(FakeSocket(), 1)
        results = await asyncio.gather(
            connection.send("Page.enable"), connection.send("Runtime.enable")
        )
        assert [item["method"] for item in results] == ["Page.enable", "Runtime.enable"]
        await connection.close()
        await connection.close()
        assert connection._pending == {}

    asyncio.run(run())


def test_cdp_timeout_cleans_pending():
    async def run():
        connection = CdpConnection(FakeSocket("silent"), 0.01)
        with pytest.raises(DianpingError) as error:
            await connection.send("Page.enable")
        assert error.value.code == "cdp_timeout"
        assert connection._pending == {}
        await connection.close()

    asyncio.run(run())


def test_cdp_error_does_not_echo_private_browser_message():
    async def run():
        connection = CdpConnection(FakeSocket("error"), 1)
        with pytest.raises(DianpingError) as error:
            await connection.send("Runtime.evaluate")
        assert error.value.code == "cdp_error"
        assert "private" not in str(error.value)
        await connection.close()

    asyncio.run(run())


def test_disconnect_rejects_pending_commands():
    async def run():
        socket = FakeSocket("silent")
        connection = CdpConnection(socket, 1)
        task = asyncio.create_task(connection.send("Page.enable"))
        await asyncio.sleep(0)
        await socket.close()
        with pytest.raises(DianpingError) as error:
            await task
        assert error.value.code == "cdp_closed"
        await connection.close()

    asyncio.run(run())
