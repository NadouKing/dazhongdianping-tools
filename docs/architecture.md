# Architecture

```text
Python application ─┐
                   ├─ DianpingClient → ChromeBrowser → local CDP WebSocket → Chrome
dp JSON CLI ────────┘                         └─ page_reader.js in the webpage
```

`DianpingClient` is an async context manager with lazy browser startup. An instance serializes collection calls and keeps its Chrome process/session warm. The last navigation timestamp enforces a two-second minimum interval by default. The library returns JSON-compatible envelopes, so the main travel application imports it without a CLI subprocess.

`ChromeBrowser` resolves an explicitly configured executable or a locally installed Chrome. It starts Chrome with a dedicated profile, an OS-selected loopback debugging port, and headless mode by default. It never connects to a daily Chrome session. A profile owner lock coordinates clients and recognizes the previous Node baseline's lock. An existing live debugger port is treated as busy, not silently attached to. Closing requests `Browser.close`, then waits and only terminates the exact child process it owns if necessary.

The CDP transport correlates command IDs over one WebSocket receive task, accepts only loopback browser endpoints, and rejects pending commands when disconnected. Remote browser errors are replaced with fixed safe messages. Normal browser startup and stdout do not dump request data.

Search navigates to `/search/keyword/<city>/0_<keyword>`. Detail navigates to the exact `/shop/<id>`. Navigation polls page location, loading state and expected selectors; modern Dianping/Meituan login hosts and verification pages are recognized before parsing. JavaScript extracts rendered fields and canonical URLs, removing tracking query parameters. Search distinguishes an explicit empty-state message from unknown markup. Detail verifies the returned ID matches the requested ID.

The current DOM path is intentional. A prior page-context `fetch` experiment returned 403. A future direct request path needs observed success, response validation, and fair latency/completeness measurements before replacing this path. CDP is a transport, not a guarantee of fewer network requests.

## Contract and limits

Success: `schemaVersion/status/source/fetchedAt/method/elapsedMs/data`. Errors: typed `DianpingError(code,message)`; CLI serializes a safe error envelope and exits nonzero. The project preserves raw localized prices, scores and business hints. Consumers decide how to normalize them and must retain source timestamps.

Only the current loaded search page and current visible detail reviews are read. `hasMore` remains null when not determined. Comments are samples, not proof of reading every review. A missing selector is unknown data. A full detail layout without a name or with the wrong shop ID is an error.

No posting, account modification, reservation or payment. No map/weather implementation: the integrating travel project continues using the existing official Amap MCP.
