# Deployment and environment

## Runtime

Use standard CPython 3.14 and uv. The production dependencies are `httpx` and `websockets`. The browser executes the packaged JavaScript itself; Node, Go, Playwright and a separately installed browser automation runtime are not required.

Chrome is an external prerequisite. The package does not download another browser. Set `DP_CHROME_PATH` if auto-discovery does not find it. Set `DP_PROFILE_DIR` to a dedicated local state directory when migrating an existing login; do not copy that directory into a Git repository or distribution.

The default state path follows the OS: Windows `%LOCALAPPDATA%`, macOS `~/Library/Application Support`, Linux `$XDG_DATA_HOME` or `~/.local/share`, then `dazhongdianping-tools/browser-profile`.

## One environment for the travel application

An integrating application pins this repository's verified commit/version as a Python dependency. Its own `uv.lock` resolves this package, Xiaohongshu tools and shared dependencies into one `.venv`. Tool repository development locks describe independent development; they do not force users to create multiple environments. Do not configure production imports through absolute checkout paths or `PYTHONPATH`.

## Session operation

1. Run `uv run dp login`. Complete login/verification in the visible dedicated Chrome window; the tool closes it when ready.
2. Run `uv run dp session`. `state=ready` means the page is accessible; `authenticated` reports known login Cookie presence without returning credentials.
3. Run searches and exact details. To avoid repeated cold browser starts from scripts, reuse one Python `DianpingClient` across calls.
4. On `login_required` or `verification_required`, finish the current command and run `login` again. On `profile_busy`, close the actual owner normally. Never delete an active browser's files or kill all Chrome processes.

The webpage can change or restrict access. `parser_unavailable` is deliberately distinguishable from a zero-result search. Saving full browser HTML/network dumps is not part of normal diagnostics.

## Release verification

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv build
uv venv --python 3.14 <temporary-clean-environment>
uv pip install --python <clean-python> dist/dazhongdianping_tools-0.1.0-py3-none-any.whl
<clean-python> -I scripts/smoke_installed_wheel.py
```

The smoke script runs children from a temporary directory and removes `PYTHONPATH`; it checks installed import, packaged JavaScript, CLI help, and JSON error behavior without starting Chrome. Run live acceptance separately with an explicitly supplied dedicated profile. Never publish the browser state with the wheel or evidence.

`docs/evidence/live-2026-10-18.json` is a sanitized historical sample, not fresh travel advice. The current official-map/weather integration belongs to the main application and is not replaced by this deployment.
