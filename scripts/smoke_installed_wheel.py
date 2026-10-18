"""Install only the supplied wheel/dependencies and check outside the checkout.

Usage: python scripts/smoke_installed_wheel.py dist/<wheel>.whl
Requires uv on PATH. Does not start Chrome or inspect login/configuration.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

LIBRARY_CHECK = """
import asyncio
import importlib.util
import sys
from importlib.resources import files
from pathlib import Path

import dazhongdianping_tools
from dazhongdianping_tools import DianpingClient, DianpingError

assert Path(dazhongdianping_tools.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert importlib.util.find_spec('lazy_trip') is None
assert importlib.util.find_spec('xiaohongshu_tools') is None
assert files('dazhongdianping_tools').joinpath('page_reader.js').read_text('utf-8')

async def check():
    async with DianpingClient() as client:
        try:
            await client.detail('invalid/path')
        except DianpingError as error:
            assert error.code == 'invalid_shop_id'
        else:
            raise AssertionError('invalid shop must be rejected before Chrome startup')
        assert client.browser.process is None

asyncio.run(check())
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    wheel = args.wheel.resolve(strict=True)
    uv = shutil.which("uv")
    if not uv:
        raise SystemExit("uv must be installed and available on PATH")
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONIOENCODING"] = "utf-8"
    with tempfile.TemporaryDirectory(
        prefix="dp-wheel-smoke-", ignore_cleanup_errors=True
    ) as directory:
        root = Path(directory)
        venv = root / "env"
        bin_dir = venv / ("Scripts" if sys.platform == "win32" else "bin")
        python = bin_dir / ("python.exe" if sys.platform == "win32" else "python")
        executable = bin_dir / ("dp.exe" if sys.platform == "win32" else "dp")

        def run(command, *, check=True):
            return subprocess.run(
                command,
                cwd=root,
                env=environment,
                check=check,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

        run([uv, "venv", "--python", sys.executable, str(venv)])
        run([uv, "pip", "install", "--link-mode", "copy", "--python", str(python), str(wheel)])
        run([str(python), "-I", "-c", LIBRARY_CHECK])
        assert "search" in run([str(executable), "--help"]).stdout
        version = run([str(executable), "--version"]).stdout.strip()
        assert version == "0.1.0"
        invalid = run([str(executable), "detail", "invalid/path"], check=False)
        assert invalid.returncode == 1 and invalid.stderr == ""
        assert json.loads(invalid.stdout)["error"]["code"] == "invalid_shop_id"
    print(
        json.dumps(
            {
                "status": "passed",
                "version": version,
                "installedOutsideSource": True,
                "consoleScript": True,
                "independentInstall": True,
                "browserStarted": False,
            }
        )
    )


if __name__ == "__main__":
    main()
