"""Run with a clean environment's Python after installing the built wheel.

Usage: <installed-python> -I scripts/smoke_installed_wheel.py
The script launches child Python processes outside the checkout with no PYTHONPATH.
It does not start Chrome or require account credentials.
"""

import asyncio
import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
from importlib.resources import files

from dazhongdianping_tools import DianpingClient, DianpingError


async def library_check():
    async with DianpingClient() as client:
        try:
            await client.detail("invalid/path")
        except DianpingError as error:
            assert error.code == "invalid_shop_id"
        else:
            raise AssertionError("invalid shop must be rejected before Chrome startup")
        assert client.browser.process is None


def main():
    distribution = importlib.metadata.distribution("dazhongdianping-tools")
    assert distribution.version == "0.1.0"
    assert files("dazhongdianping_tools").joinpath("page_reader.js").read_text("utf-8")
    asyncio.run(library_check())
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    with tempfile.TemporaryDirectory(prefix="dp-wheel-smoke-") as outside:
        help_result = subprocess.run(
            [sys.executable, "-I", "-m", "dazhongdianping_tools.cli", "--help"],
            cwd=outside,
            env=environment,
            capture_output=True,
            check=True,
        )
        assert b"search" in help_result.stdout
        invalid = subprocess.run(
            [sys.executable, "-I", "-m", "dazhongdianping_tools.cli", "detail", "invalid/path"],
            cwd=outside,
            env=environment,
            capture_output=True,
        )
        assert invalid.returncode == 1
        assert json.loads(invalid.stdout)["error"]["code"] == "invalid_shop_id"
    print(json.dumps({"status": "ok", "version": distribution.version, "browserStarted": False}))


if __name__ == "__main__":
    main()
