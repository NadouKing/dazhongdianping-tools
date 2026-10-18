"""Own one dedicated Chrome process; never attach to or kill a daily browser."""

import asyncio
import contextlib
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx

from .cdp import CdpConnection
from .errors import DianpingError


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        # os.kill(pid, 0) is not used on Windows: never send a termination signal.
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() == 5  # Access denied is not proof of death.
        code = ctypes.c_ulong()
        try:
            if not kernel.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel.CloseHandle(ctypes.c_void_p(handle))
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class ProfileLock:
    def __init__(self, profile: Path):
        self.profile = profile
        self.path = profile / "dianping-tools-owner.lock"
        self.token = uuid.uuid4().hex
        self.owned = False
        self._guard = None

    def _take_guard(self):
        # OS locking serializes stale-lock recovery as well as ordinary acquisition.
        # The stable guard file is never unlinked, avoiding inode/replacement races.
        self._guard = (self.profile / "dianping-tools.guard").open("a+b")
        try:
            if self._guard.seek(0, 2) == 0:
                self._guard.write(b"\0")
                self._guard.flush()
            self._guard.seek(0)
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(self._guard.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._guard.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._guard.close()
            self._guard = None
            raise DianpingError("profile_busy", "专用点评目录正由其他命令使用。") from None

    def _release_guard(self):
        if self._guard:
            self._guard.close()  # Closing the handle releases the OS lock.
            self._guard = None

    def acquire(self):
        self.profile.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._take_guard()
        try:
            self._acquire_owner()
        except BaseException:
            self._release_guard()
            raise

    def _acquire_owner(self):
        legacy = self.profile / "daytrip-owner.lock"
        if legacy.exists():
            try:
                if process_alive(int(legacy.read_text(encoding="utf-8").strip())):
                    raise DianpingError("profile_busy", "专用点评目录正由其他工具使用。")
            except ValueError, OSError:
                pass
        for _ in range(2):
            try:
                with self.path.open("x", encoding="utf-8") as file:
                    json.dump({"pid": os.getpid(), "token": self.token}, file)
                self.owned = True
                return
            except FileExistsError:
                try:
                    existing = json.loads(self.path.read_text(encoding="utf-8"))
                    pid = int(existing.get("pid", 0))
                except OSError, ValueError, TypeError:
                    # A partial or foreign lock is treated conservatively.
                    raise DianpingError("profile_busy", "专用点评目录的锁尚未释放。") from None
                if process_alive(pid):
                    raise DianpingError("profile_busy", "专用点评目录正由其他命令使用。") from None
                with contextlib.suppress(FileNotFoundError):
                    self.path.unlink()
        raise DianpingError("profile_busy", "无法取得点评专用目录锁。")

    def release(self):
        if not self.owned:
            self._release_guard()
            return
        try:
            current = json.loads(self.path.read_text(encoding="utf-8"))
            if current.get("token") == self.token:
                self.path.unlink()
        except OSError, ValueError:
            pass
        self.owned = False
        self._release_guard()


def default_profile() -> Path:
    if os.environ.get("DP_PROFILE_DIR"):
        return Path(os.environ["DP_PROFILE_DIR"]).expanduser().resolve()
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "dazhongdianping-tools" / "browser-profile"


def chrome_executable(explicit: str | Path | None) -> str:
    configured = explicit or os.environ.get("DP_CHROME_PATH")
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())
        raise DianpingError("browser_not_found", "指定的 Chrome 可执行文件不存在。")
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if found := shutil.which(name):
            return found
    candidates = [Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")]
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        if root := os.environ.get(variable):
            candidates.append(Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe")
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise DianpingError("browser_not_found", "未找到 Chrome；请设置 DP_CHROME_PATH。")


def validate_dedicated_profile(profile: Path):
    roots = []
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        roots = [
            base / "Google" / "Chrome" / "User Data",
            base / "Chromium" / "User Data",
            base / "Microsoft" / "Edge" / "User Data",
        ]
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
        roots = [base / "Google" / "Chrome", base / "Chromium", base / "Microsoft Edge"]
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        roots = [base / "google-chrome", base / "chromium", base / "microsoft-edge"]
    if any(profile.is_relative_to(root.resolve()) for root in roots):
        raise DianpingError("invalid_profile", "请使用独立专用目录，不能使用日常浏览器目录。")


class ChromeBrowser:
    def __init__(self, profile_dir=None, chrome_path=None, headless=True, timeout=30.0):
        self.profile = (
            Path(profile_dir).expanduser().resolve() if profile_dir else default_profile()
        )
        validate_dedicated_profile(self.profile)
        self.chrome_path = chrome_path
        self.headless = headless
        self.timeout = timeout
        self.lock = ProfileLock(self.profile)
        self.process: asyncio.subprocess.Process | None = None
        self.cdp: CdpConnection | None = None

    async def _active_endpoint(self):
        try:
            lines = (self.profile / "DevToolsActivePort").read_text(encoding="utf-8").splitlines()
            port = int(lines[0])
            path = lines[1]
            if not (0 < port < 65536 and path.startswith("/devtools/browser/")):
                return None
            return f"ws://127.0.0.1:{port}{path}"
        except OSError, ValueError, IndexError:
            return None

    async def _existing_browser_alive(self):
        endpoint = await self._active_endpoint()
        if not endpoint:
            return False
        port = endpoint.split(":", 2)[2].split("/", 1)[0]
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=1) as client:
                response = await client.get(f"http://127.0.0.1:{port}/json/version")
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def start(self):
        if self.cdp:
            return self
        executable = chrome_executable(self.chrome_path)
        self.lock.acquire()
        try:
            if await self._existing_browser_alive():
                raise DianpingError("profile_busy", "该专用目录已有浏览器运行，请先正常关闭它。")
            with contextlib.suppress(FileNotFoundError):
                (self.profile / "DevToolsActivePort").unlink()
            args = [
                executable,
                "--remote-debugging-port=0",
                "--remote-debugging-address=127.0.0.1",
                f"--user-data-dir={self.profile}",
                "--no-first-run",
                "--no-default-browser-check",
                "--lang=zh-CN",
                "--window-size=1440,960",
                *(["--headless=new"] if self.headless else []),
                "about:blank",
            ]
            creationflags = (
                subprocess.CREATE_NO_WINDOW if sys.platform == "win32" and self.headless else 0
            )
            self.process = await asyncio.create_subprocess_exec(
                *args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            deadline = time.monotonic() + self.timeout
            while time.monotonic() < deadline:
                if self.process.returncode is not None:
                    raise DianpingError(
                        "browser_start_failed", "Chrome 未能启动，专用目录可能被其他浏览器占用。"
                    )
                if endpoint := await self._active_endpoint():
                    self.cdp = await CdpConnection.open(endpoint, self.timeout)
                    return self
                await asyncio.sleep(0.1)
            raise DianpingError("browser_start_timeout", "等待专用 Chrome 启动超时。")
        except BaseException:
            await self.close()
            raise

    async def close(self):
        if self.cdp:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self.cdp.send("Browser.close"), timeout=3)
            await self.cdp.close()
            self.cdp = None
        if self.process and self.process.returncode is None:
            try:
                await asyncio.wait_for(self.process.wait(), timeout=3)
            except TimeoutError:
                # This exact process was started by this object. Never terminate by name/profile.
                with contextlib.suppress(ProcessLookupError):
                    self.process.terminate()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self.process.wait(), timeout=3)
        self.process = None
        self.lock.release()
