# Local regression check — 2026-10-28

Scope: the complete uncommitted submission-review changes relative to `de01555`, including the app, MCP runner and transport, deployment scripts, tool annotations, skills, and OpenAI package builder. Nothing deployed.

## Regressions found and corrected

1. The new gateway bridge used a fixed 10-second upstream timeout, shortening existing instrument-download and historical-query allowances. It now applies the library's endpoint timeout policy plus the existing gateway allowance: instruments 125 seconds, historical 35 seconds, ordinary requests 20 seconds. Added a real Unix-socket bridge test checking the forwarded timeout values. Request handling uses daemon worker threads so ending a run does not wait for a slow upstream handler; request-budget accounting is locked across workers. Upstream requests already dispatched may finish after a run ends, as before; these are read requests and the run token is revoked.
2. The instruments cache used PID-based temporary filenames. Separate sandbox PID namespaces can reuse the same PID while building the same user's cache concurrently. Cache builds now reserve unique temporary files atomically, replace the completed cache atomically, and clean temporary files on failure. Added a concurrent-build regression test that forces both builders to overlap.

## Verification results

- MCP/Python: **52 passed, 6 skipped**, with local test PostgreSQL and Unix sockets accessible. Ruff lint/format and strict mypy passed.
- App: **12 tests passed**, TypeScript and Biome passed.
- Production app build: **passed**. The initial restricted invocation could not bind Turbopack's local port; rerunning with the necessary local process/port access succeeded.
- OpenAI package: **8 tests passed**; archive rebuilt and verified.
- Four changed deployment shell scripts: `bash -n` passed. `git diff --check` passed.

Passing coverage includes account reads, quotes/batching, symbol resolution, options calculations, indicators, transport/error/rate-limit behavior, OAuth login and refresh, CIMD/resource binding, gateway authorization and write rejection, disconnected-account behavior, tool metadata, frontend helpers, and package integrity. These are local tests using synthetic broker responses, not a live Zerodha session or full browser journey.

## Intentional behavior changes and remaining release checks

- `run_python` now requires Linux plus usable bubblewrap. macOS script execution is disabled. Six Linux execution tests were skipped here: actual namespace isolation, socket transport from the sandbox, end-to-end broker execution, token-expiry/watcher interaction, watcher lifecycle, and OpenAI script timeout behavior. These must pass on Linux before release.
- The service now runs a sandbox preflight before starting. A host with incompatible namespace/systemd restrictions will refuse service startup, affecting app backend availability as well as script execution. Shell syntax checks do not validate this deployment interaction; run preflight under the actual service restrictions on staging first.
- Scripts can access their persistent workspace and permitted Kite reads. Arbitrary networking, host paths, host executables, and other tenants' files are deliberately unavailable. Existing scripts depending on those facilities will fail.
- Cache is now per user. First use downloads/builds a fresh instruments cache for each user; this can increase latency and broker requests. Full production-size dump performance under the new 512 MiB address-space, 64 MiB per-file, and 128-descriptor limits remains unmeasured. Complex workloads exceeding these limits may fail.
- Relative saved-data access remains supported by design; scripts that saved absolute host workspace paths need `/workspace` paths. New script archives live outside the user workspace; older `_runs` archives are not migrated.
- Corrected write/destructive annotations can cause clients to request additional confirmation for `run_python`.
- Retention scheduling, total resource/disk quotas, buffered output growth, and the other open submission-review findings remain open. Passing regression tests does not resolve them.

Conclusion: two concrete regressions were fixed and all runnable checks passed. This is not yet evidence of full compatibility on the production Linux host; Linux execution, staging service startup, and representative large analyses remain required before deployment.
