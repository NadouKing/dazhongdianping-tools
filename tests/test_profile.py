import json
import os

import pytest

from dazhongdianping_tools.browser import ChromeBrowser, ProfileLock, process_alive
from dazhongdianping_tools.errors import DianpingError


def test_current_process_detected_without_signals():
    assert process_alive(os.getpid())
    assert not process_alive(-1)


def test_active_profile_lock_blocks_other_client(tmp_path):
    first, second = ProfileLock(tmp_path), ProfileLock(tmp_path)
    first.acquire()
    try:
        with pytest.raises(DianpingError) as error:
            second.acquire()
        assert error.value.code == "profile_busy"
        second.release()
        assert first.path.exists()
    finally:
        first.release()
    assert not first.path.exists()


def test_stale_lock_is_recovered(tmp_path, monkeypatch):
    (tmp_path / "dianping-tools-owner.lock").write_text(json.dumps({"pid": 123, "token": "old"}))
    monkeypatch.setattr("dazhongdianping_tools.browser.process_alive", lambda _: False)
    lock = ProfileLock(tmp_path)
    lock.acquire()
    assert json.loads(lock.path.read_text())["token"] == lock.token
    lock.release()


def test_legacy_baseline_owner_is_respected(tmp_path):
    (tmp_path / "daytrip-owner.lock").write_text(str(os.getpid()))
    with pytest.raises(DianpingError) as error:
        ProfileLock(tmp_path).acquire()
    assert error.value.code == "profile_busy"


def test_release_cannot_delete_another_owners_lock(tmp_path):
    lock = ProfileLock(tmp_path)
    lock.acquire()
    lock.path.write_text(json.dumps({"pid": os.getpid(), "token": "other"}))
    lock.release()
    assert lock.path.exists()


def test_operating_system_lock_blocks_even_with_stale_metadata(tmp_path, monkeypatch):
    first, second = ProfileLock(tmp_path), ProfileLock(tmp_path)
    first.acquire()
    try:
        monkeypatch.setattr("dazhongdianping_tools.browser.process_alive", lambda _: False)
        with pytest.raises(DianpingError) as error:
            second.acquire()
        assert error.value.code == "profile_busy"
        assert json.loads(first.path.read_text())["token"] == first.token
    finally:
        first.release()


def test_default_daily_chrome_profile_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr("dazhongdianping_tools.browser.sys.platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    with pytest.raises(DianpingError) as error:
        ChromeBrowser(profile_dir=tmp_path / "Google" / "Chrome" / "User Data")
    assert error.value.code == "invalid_profile"
