# Repository instructions

Before any change, read `docs/development-delivery.md`; create/sync the task branch first. Every feature/fix needs relevant live read-only acceptance, updated evidence and a draft PR attached to the chat. Use `.github/PULL_REQUEST_TEMPLATE.md`, handle reviews with `docs/review.md`, and do not merge before the user's explicit request.

This is `dazhongdianping-tools`, an independent Python 3.14 package and `dp` CLI for read-only Dianping collection. It is a library dependency of `lazy-trip`, not an agent host or map/weather provider.

## Boundaries and layers

- `cli.py`: argument parsing, JSON output and exit status only. Never embed browser logic here.
- `client.py`: city/search/detail/session contract, serialization, navigation and data validation.
- `page_reader.js`: runs inside Chrome through `Runtime.evaluate`. Package it as a resource; no Node runtime.
- `cdp.py`: local-only WebSocket protocol, command correlation, timeout/disconnect behavior; no platform business.
- `browser.py`: owns one exact dedicated Chrome process, profile lock and idempotent cleanup. Never terminate processes by name or attach to a user's daily browser.
- `errors.py`: typed, credential-safe library errors. Do not return raw Chrome errors, request headers, cookies or signed URLs to CLI users.

Main application imports this package directly. Do not add a dependency on `lazy-trip` or Xiaohongshu tools. Official Amap/weather remains the main application's existing MCP connection.

## Data and session rules

- Read-only collection only. No account interaction, purchase, CAPTCHA solving or generic network bypass.
- Preserve local login directories. Never commit/package profile data, cookies, private absolute paths, headers, signatures or runtime dumps.
- Normalize shop URLs to canonical `https://www.dianping.com/shop/<id>`; reject identity mismatches.
- Authentication, verification, changed markup and genuine empty results are different states. Empty parsing is not automatically an empty search result.
- Unknown fields remain null. `not_visible_on_page` does not mean zero reviews. Preserve raw prices/times and `fetchedAt`; a relative opening hint is not a full business schedule.
- Prefer proven direct HTTP or page-context request paths if later verified. Current implementation deliberately uses working CDP navigation/DOM; page `fetch` previously returned 403. Do not claim better speed without comparable measurements.

## Development checks

Use `uv sync --locked`; then `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest -q`. For changes to loading, parsing or profile lifecycle, test relevant failure cases as well as successful data.

Build with `uv build`. Install the wheel into a clean environment, clear `PYTHONPATH`, and run `scripts/smoke_installed_wheel.py` outside the checkout. This catches missing package resources and accidental source imports.

Live tests are opt-in and serial for a given profile. Use only an explicitly supplied dedicated directory; always close in `finally`/`async with`. Retain a sanitized acceptance summary, not private browser material. Documentation-only edits do not need another live platform request.

Update README/contracts when behavior changes. Keep new integrations small and justified by an actual gap. The engineering structure is inspired by seller-ops-automation; its seller operations, credentials and approval rules do not apply here.
