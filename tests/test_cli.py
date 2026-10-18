import json
import sys

from dazhongdianping_tools.cli import main


def test_invalid_cli_arguments_are_safe_json(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["dp", "search"])
    assert main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result["error"]["code"] == "invalid_arguments"


def test_library_error_reaches_cli_as_json(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["dp", "detail", "invalid/path?secret=private"])
    assert main() == 1
    output = capsys.readouterr().out
    assert json.loads(output)["error"]["code"] == "invalid_shop_id"
    assert "private" not in output
