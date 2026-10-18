# Deployment and environment

Final maintenance snapshot dated 2026-10-18; no further active maintenance is planned. Archival is left to the owner after reviewing the final PR.

## Runtime

Use standard CPython 3.14 and uv. The production dependencies are `httpx` and `websockets`. The browser executes the packaged JavaScript itself; Node, Go, Playwright and a separately installed browser automation runtime are not required.

Chrome is an external prerequisite. The package does not download another browser. Set `DP_CHROME_PATH` if auto-discovery does not find it. Set `DP_PROFILE_DIR` to a dedicated local state directory when migrating an existing login; do not copy that directory into a Git repository or distribution.

The default state path follows the OS: Windows `%LOCALAPPDATA%`, macOS `~/Library/Application Support`, Linux `$XDG_DATA_HOME` or `~/.local/share`, then `dazhongdianping-tools/browser-profile`.

## One environment for the travel application

This package works alone: clone only this repository and run `uv sync --locked`, or install its built wheel into a Python 3.14 environment. Both the library and `dp` CLI are independent entry points. No other platform package or travel application is required.

An integrating application may pin this repository's verified commit/version as a Python dependency and share its own `.venv`. It owns business adaptation, while this tool owns the platform contract. Tool repository development locks do not force application users to create multiple environments. Do not configure production imports through absolute checkout paths or `PYTHONPATH`.

## Session operation

1. Run `uv run dp login`. Complete login/verification in the visible dedicated Chrome window; the tool closes it when ready.
2. Run `uv run dp session`. `state=ready` means the page is accessible; `authenticated` reports known login Cookie presence without returning credentials.
3. Run searches and exact details. To avoid repeated cold browser starts from scripts, reuse one Python `DianpingClient` across calls.
4. Search-page login does not guarantee detail access. To complete a gate on the actual detail page, opt in with `dp --visible --verification-wait 180 detail <id>`. The same tab stays open for bounded human interaction; no refresh, re-navigation or automatic solving. A persistent gate returns `verification_timeout`. Default queries still fail immediately. On `profile_busy`, close the actual owner normally. Never delete an active browser's files or kill all Chrome processes.

The webpage can change or restrict access. `parser_unavailable` is deliberately distinguishable from a zero-result search. Saving full browser HTML/network dumps is not part of normal diagnostics.

## Release verification

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv build
uv run python scripts/smoke_installed_wheel.py dist/dazhongdianping_tools-0.1.0-py3-none-any.whl
```

The smoke script creates a temporary clean environment, installs only the supplied wheel and declared dependencies, removes `PYTHONPATH` and runs isolated children outside the checkout. It checks installed import, packaged JavaScript, the console entry point and JSON errors without starting Chrome, and verifies no consumer application or other platform tool is installed. CI runs the same check. Run live acceptance separately with an explicitly supplied dedicated profile. Never publish browser state with the wheel or evidence.

`docs/evidence/live-2026-10-18.json` is a sanitized historical sample, not fresh travel advice. The current official-map/weather integration belongs to the main application and is not replaced by this deployment.
