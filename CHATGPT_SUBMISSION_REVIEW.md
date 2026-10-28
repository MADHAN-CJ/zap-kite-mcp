# ChatGPT public plugin / MCP submission review

Initially reviewed 28 October 2026 against checkout `031fb00b01aa7f9b323f9dfc63b98579adc2cbb5` and the public endpoints. Re-reviewed the updated local checkout `de01555` on the same date. This is an independent readiness review, not an OpenAI approval decision. Application code was not changed.

**Verdict: local changes are not yet ready for public submission.** The execution security model, tool surface, reviewer access, and packaging findings remain. Production deployment is intentionally deferred until review changes are satisfied; this is not a defect in the local implementation. A working custom MCP connection does not establish public listing eligibility.

## Local re-review of `de01555`

Compared the entire tracked diff against the original reviewed commit. Only seven files changed: the CI workflow, README, package scripts, and four production deployment files. There are no changes to `mcp/src`, `mcp/tests`, `plugin`, web application code, or web tests. The untracked review document is the only working-tree addition.

| Original finding | Updated disposition | Reason |
| --- | --- | --- |
| 1. Script isolation | **Still applicable; production configuration adds concrete exposure** | Runner unchanged; all customers still execute as one service identity. See production details below. |
| 2. Generic executor | **Accepted submission risk; retain `run_python`** | User reaffirmed the architecture on 28 October; prior decision recorded in `docs/plan-v1.md:177`. OpenAI acceptance remains unverified. |
| 3. Read-only annotation | **Fixed locally; live rescan pending** | `run_python` now advertises write-capable, potentially destructive, non-idempotent behavior within a bounded account/workspace. |
| 4. Reviewer access | **Owner-managed operational dependency** | User elected to refresh the reviewer broker session manually throughout review. No demo mode requested; unattended-access acceptance remains a review risk. |
| 5. Production/source mismatch | **Deferred release verification, not a local-code defect** | Deployment is intentionally pending. The local ChatGPT additions already existed at the first review. Recheck the deployed build only after the approved release. |
| 6. OpenAI package | **Prepared and checked locally; portal validation pending** | Separate Codex-compatible OpenAI ZIP, explicit OAuth configuration, canonical skill, listing metadata, and archive checks added. |
| 7. Consent disclosure | **Still applicable** | Login copy and permissions unchanged. |
| 8. CIMD fetch restrictions | **Still applicable** | Fetch implementation unchanged. |
| 9. Script retention | **Still applicable** | Cleanup implementation unchanged; no scheduled cleanup added. |
| 10. Resource/latency bounds | **Still applicable** | Runner unchanged; production unit retains service-wide rather than per-job limits. |
| 11. Missing resource binding | **Still applicable** | Token acceptance logic unchanged. |

### Additional production evidence for finding 1

`deploy/setup-prod.sh:34` makes `/opt/zap-kite-mcp-prod/.env` owned by `zapkiteprod`, with mode 600. `deploy/zap-kite-mcp-prod.service:7` runs the service as that same user, and Runner starts scripts without changing identity. The supplied configuration therefore lets a script read the service's secrets file. `ProtectSystem=strict` restricts writes; it does not make that file unreadable. Environment scrubbing cannot prevent reading secrets back from disk. This is inferred directly from the supplied configuration; no actual secret file was read.

Additionally, `deploy/setup-prod.sh:7` installs Python under `/var/lib/zapkiteprod/python`, and the service's `ReadWritePaths=/var/lib/zapkiteprod` includes that runtime. Submitted scripts inherit this writable filesystem scope. This creates a runtime-tampering/persistence risk in addition to cross-user workspace access. Keep the interpreter and dependencies immutable to execution workers, keep service secrets outside their mounts/identity, and isolate each job. Making only the `.env` file root-owned would not resolve the broader runner flaw.

Production/staging separation is improved through a distinct OS user, state path, and database search path. However, the README explicitly says database schemas share an owner; a search path is not a database authorization boundary. That distinction matters especially while submitted scripts can read database credentials.

### Reviewer login clarification

`deploy/update-prod.sh:25` permits development-login settings only for `test@slash.markets` with a nonempty code. This is useful progress toward unattended sign-in, but does not create an isolated demo identity, populate data, or prevent the underlying Zerodha session expiring. The README's instruction that development overrides must always be disabled in production also conflicts with this explicit reviewer exception and should be reconciled.

### Re-review validation

- Inspected the complete tracked diff from `031fb00` to `de01555`, including all new production scripts, the service unit, nginx configuration, and CI/package changes.
- `bash -n deploy/setup-prod.sh deploy/update-prod.sh`: passed. This checks shell syntax, not live provisioning or service isolation.
- Previous application-test results remain historical evidence; unchanged application suites and unchanged synthetic proofs were not rerun solely for this deployment-only diff.
- Did not contact production, execute deployment scripts, push commits, inspect credentials, or change application code during this re-review.
- Third-party authorization, publisher verification, and a real ChatGPT/portal acceptance test remain unverified external prerequisites.

## Findings, in priority order

### Implementation update — finding 1

A local remediation now replaces host execution with a mandatory Linux Bubblewrap
boundary, a per-job read-only gateway socket, private workspace/cache mounts, and
read-only runtime mounts. Host-side script archives have moved out of user-writable
workspaces. Production and staging units include a real sandbox startup preflight.
See `SANDBOX.md`, `mcp/src/zap_kite_mcp/sandbox.py`, and `mcp/tests/test_sandbox.py`.

**Status: implemented locally, Linux validation pending; not yet closed.** The original
finding and reproduction below describe the pre-change runner. macOS cannot execute
the Linux namespace tests. No deployment or push has been performed. The generic
executor, annotation, retention, and full resource-quota findings remain separate.

### 1. Critical — Python execution does not isolate users

Evidence: `mcp/src/zap_kite_mcp/runner.py:47`, `:89`; `deploy/zap-kite-mcp.service:7`.

Every script runs as the service OS user. Changing its working directory and HOME, scrubbing environment variables, and passing `python -I` do not restrict filesystem access. The systemd unit restricts the service as a whole, not individual customers; all workspaces are under the same writable state directory. Scripts also retain general Python imports and network access.

**Reproduced locally:** using the actual Runner with two fake users and a synthetic sentinel in a temporary directory, user A read and overwrote user B's file using `../fake-user-b/sentinel.txt`. No real user data or credentials were accessed. Deployed exploitation was not attempted.

Impact: confidential workspace data and scripts can cross account boundaries; an arbitrary script can access whatever else the service identity can read or modify. Consequently, the read-only Kite gateway is not a complete security boundary.

Fix before public use: remove arbitrary execution from the public tool surface, or implement real per-run OS/container isolation with scoped mounts, separate identities, denied general network egress, a narrowly scoped gateway, resource quotas, and process-tree cleanup. Add negative cross-user, host-file, network-egress, and child-process isolation tests. Changing annotations alone does not fix this.

### 2. High — Accepted directory-review risk for the retained Python analytics tool

Evidence: `mcp/src/zap_kite_mcp/server.py:240`, `:267`; `mcp/src/zapkite/schema.py`; `plugin/skills/slash-markets-kite-data/SKILL.md`.

The principal interface is `run_python(code)`, with account reads, quotes, candles, option chains, indicators, and API discovery encoded in Python. OpenAI requires individually exposed, reviewable model-callable operations and explicitly restricts generic executors used to expose undisclosed operations. This remains a strong rejection risk, even after sandboxing. The wording does not establish a blanket prohibition on every Python execution tool, nor does documenting an internal library automatically satisfy individual operation exposure. [Plugin guidelines](https://developers.openai.com/plugins/plugin-guidelines#tool-independence-and-exposure).

**Architecture decision, reaffirmed 28 October:** retain `run_python`. `docs/plan-v1.md:177` records the same user decision on 26 October, including acceptance of this review risk. The initial recommendation to replace it did not account for that decision and is superseded. The skill explicitly describes the reason: compose dependent data reads and calculations on the server, keep intermediate rows out of model context, and return compact conclusions. Fixed preselected analysis tools cannot preserve all of that open-ended analytical flexibility.

Recommended submission case: describe the tool accurately as bounded Python analysis of the connected user's Kite data, publish the complete accessible library and gateway allowlist for review, keep scheduling/email actions in separately exposed tools, and document persistent workspace effects honestly. Include representative complex-query traces and measured context/output sizes; do not claim unmeasured speed or accuracy improvements. The broad `kite_get` read helper should be documented precisely, with its gateway-enforced limits, rather than described as unrestricted API access. Do not hide capabilities, change names to evade review, or claim that safety controls waive directory rules.

**Disposition:** accepted product/submission tradeoff, not resolved policy compliance. Preserve the interface while fixing security, annotations, consent, packaging, and other objective defects. Seek a documented OpenAI decision on this exact contract through submission/review before treating public listing as assured. No replacement tool surface is authorized by this review decision.

### 3. High — `run_python` is incorrectly advertised as read-only

**Remediation, 28 October:** fixed locally. `run_python` now emits
`readOnlyHint=false`, `destructiveHint=true`, `idempotentHint=false`, and
`openWorldHint=false`. The last value reflects the sandbox's bounded workspace and
fixed Kite read gateway, not arbitrary internet access. Its description and both
copies of the skill disclose persistent creation, overwriting, and deletion of
workspace files while distinguishing read-only broker access. The tool's name,
arguments, output format, and analytical workflow are retained. The actual MCP
`tools/list` response is covered by integration assertions. Production rescan is
deferred until deployment. The paragraph below records the original defect.

Evidence: `mcp/src/zap_kite_mcp/server.py:271`; `mcp/src/zap_kite_mcp/runner.py:79`; skill instructions explicitly encourage persistent files.

The tool advertises `readOnlyHint=true` and `destructiveHint=false`, while caller code can persist, overwrite, and delete workspace files. The synthetic cross-user test also demonstrates writes outside the intended workspace. The annotation is therefore inaccurate independently of whether Kite order placement is exposed. OpenAI treats persistent artifacts and other state changes as writes. [Annotation requirements](https://developers.openai.com/plugins/plugin-guidelines#correct-annotation).

Fix: make the public computation path actually bounded and read-only, or annotate permitted writes accurately after securing execution. Audit `create_watcher` separately: it is correctly marked as a write, but it also runs supplied code and initiates future emails, which must be reflected in its eventual behavior and annotation review.

### 4. High — No demonstrated reviewer account that works unattended

Evidence: `plugin/README.md:20`; `mcp/src/zap_kite_mcp/identity.py:32`; `mcp/src/zap_kite_mcp/server.py:460`; README documents daily Zerodha session expiry.

Normal access needs an emailed OTP followed by a separate Zerodha connection, and that broker session expires daily. Reviewers cannot reliably exercise tools without inbox access and repeated broker sign-in. `DEV_LOGIN_EMAIL` / `DEV_LOGIN_CODE` can bypass the first step for one account, but do not supply a persistent broker demo or sample portfolio. Production reviewer configuration was not inspected.

Provide a dedicated, isolated demo identity with synthetic representative data and stable reviewer credentials. It must cover all listed capabilities without developer assistance, real brokerage credentials, mailbox access, or daily login maintenance. Do not simply expose a broad production development bypass. OpenAI requires fully functional reviewer access without extra verification/configuration. [Review requirements](https://developers.openai.com/plugins/deploy/app-review#review-and-approval-faqs).

### 5. Deferred release check — Production does not yet expose the local ChatGPT additions

**Re-review disposition:** intentionally pending deployment, per the user's release plan. The observations below are historical results from the initial review, not a newly discovered local-code blocker. Run these checks again after the approved build is deployed.

Evidence: public HTTPS probes on 28 October 2026; source `mcp/src/zap_kite_mcp/server.py:425`, `:436`, `:576` and `oauth.py`.

| Probe | Observed result |
| --- | --- |
| `/health` | HTTP 200 |
| Unauthenticated MCP initialize at `/` | HTTP 401 with a protected-resource metadata challenge |
| `/.well-known/oauth-protected-resource` | HTTP 200; canonical resource `https://mcp.slash.markets/` |
| `/.well-known/oauth-authorization-server` | HTTP 200; only `kite:read`, DCR, client-secret authentication, and S256 advertised |
| `/userinfo` | HTTP 404 |
| `/.well-known/openai-apps-challenge` | HTTP 404 |
| `https://app.slash.markets/privacy` and `/terms` | Both HTTP 200 |

The deployed metadata lacks the checkout's CIMD flag, `none` token-endpoint authentication, `openid`/`email` scopes, UserInfo, and authorization-response issuer flag. DCR remains supported, so these observations do **not** prove all ChatGPT connections fail. They do prove the deployment cannot be certified using this checkout's behavior. Workspace domain-restriction support and domain verification remain incomplete at this hostname.

Deploy the reviewed build to the exact submitted endpoint, configure the portal's challenge token, and recheck discovery and authenticated tool scanning. An allowed-parent domain challenge or existing portal verification was not inspected. [Authentication](https://developers.openai.com/plugins/build/auth), [domain and workspace setup](https://developers.openai.com/plugins/guides/submit-claude-plugin#prepare-and-submit-the-mcp-server).

### 6. High — The supplied package is not a validated OpenAI MCP submission package

**Remediation, 28 October:** separate source metadata now lives in `plugin-openai/`.
`npm run plugin:openai:build` assembles a Codex-compatible ZIP containing
`.codex-plugin/plugin.json`, `.mcp.json`, the canonical skill, existing icon,
README, and license. The metadata includes OAuth with CIMD preference, scopes,
listing fields, five positive and three negative review cases, and release notes.
The existing Claude package is preserved. Eight package tests cover the actual ZIP,
reproducibility, unexpected files, credentials/headers, missing skills, asset path
escapes, listing limits, and endpoint selection. These are local contract checks,
not official portal validation. See `OPENAI_PLUGIN.md` for the documented portable
schema mismatch that motivated the supported compatibility layout and the remaining
video, credentials, country selection, verification, and live tool scan steps.
The original finding below is retained as review history.

Evidence: `plugin/.claude-plugin/plugin.json:1`, `plugin/.mcp.json:1`, `plugin/README.md:1`, `tests/plugin.test.ts:22`.

The folder contains a Claude manifest and Claude-facing installation copy. It lacks a root Agent Plugins manifest or a Codex compatibility manifest. Its tests only check selected Claude fields and a URL; they do not validate OpenAI package schemas, authentication configuration, or portal ingestion.

This is not a claim that all Claude archives are rejected: OpenAI documents direct conversion for skills-only uploads. That path must not be used to accidentally omit this plugin's required MCP server. Prepare a **With MCP** package with both server and skill from the start. Prefer root `plugin.json` plus `mcp.json` using the documented schemas, or the supported Codex compatibility layout. Configure the chosen OAuth registration method, presentation fields, icon, policy/support links, and review details in the appropriate schema. Replace “inside Claude” and Claude-only install instructions. Upload only the curated package, never the repository with local environment files.

[Package format](https://developers.openai.com/plugins/build/plugins), [Claude migration](https://developers.openai.com/plugins/guides/submit-claude-plugin), [submission flow](https://developers.openai.com/plugins/deploy/submission).

### 7. High — OAuth consent understates the granted capabilities

Evidence: `mcp/src/zap_kite_mcp/server.py:450`, `:468`, `:355`; `mcp/src/zap_kite_mcp/config.py:10`.

The login copy describes access as read-only account analysis. The same authorization permits arbitrary script execution, persistent workspace files, and creating scheduled email watchers. There is no distinct watcher permission and the login page does not identify the requesting client or explain these side effects before authorization completes.

Show the requesting client, accessed account data, analysis execution/storage, and watcher/email permissions in an explicit consent step. Consider separate account-read and watcher-write scopes with server-side enforcement. OpenAI requires transparent, necessary permissions. [Permission guidance](https://developers.openai.com/plugins/plugin-guidelines#authentication-and-permissions).

### 8. High — CIMD fetching permits requests to private-network destinations via DNS

Evidence: `mcp/src/zap_kite_mcp/oauth.py:69`, `:112`.

The client-ID validator rejects literal IP addresses, localhost, and `.local`, but accepts other HTTPS hostnames without checking resolved addresses. `_client_from_cimd` then fetches the URL. An attacker-controlled hostname can resolve to loopback/private/link-local destinations; rejecting IP literals does not prevent that. This is a code-level finding; no private-network endpoint was contacted during review.

Use a hardened fetch path with DNS/IP validation at connection time, private-range denial, bounded streaming response reads, controlled ports, and no redirects. The current 64 KB check occurs after the response has already been buffered. This affects the new CIMD implementation and should be fixed before deploying it publicly.

### 9. Medium — The 24-hour script-retention promise is not enforced

Evidence: `app/privacy/page.tsx:63`, `:234`; `mcp/src/zap_kite_mcp/runner.py:82`, `:138`.

Old scripts are pruned only when that same user runs another script. Inactive users' scripts can therefore remain indefinitely. A temporary-directory reproduction confirmed an expired synthetic script survived another user's run. The privacy policy promises deletion within 24 hours.

Add scheduled cleanup independent of user activity and monitor its success. Document deletion of workspace files and account records as an operational procedure as well. The presence of a manual deletion contact is not itself a defect; the confirmed issue is the unenforced script deadline. [Privacy requirements](https://developers.openai.com/plugins/plugin-guidelines#privacy-policy).

### 10. Medium — Execution limits do not bound resource use or end-to-end latency

Evidence: `mcp/src/zap_kite_mcp/runner.py:99`, `:108`; `server.py:261`, `:287`, `:373`; `watchers.py:172`; service `MemoryMax=1G`.

Output is fully buffered by `communicate()` before truncation. A noisy script can exhaust the shared process/service memory before the advertised output cap applies. There is no per-run memory/disk/process quota. The 50-second OpenAI cap covers only a detected host's `run_python` execution; time waiting for the global semaphore is outside it, and watcher dry runs use the normal runner timeout.

Stream and cap stdout/stderr while the process runs, impose per-job quotas, bound queue wait, and apply a total request deadline to both script and watcher creation. Treat 50 seconds as this implementation's design choice, not an established OpenAI contractual timeout.

### 11. Medium — Tokens without a resource binding are still accepted

Evidence: `mcp/src/zap_kite_mcp/server.py:258`; `mcp/src/zap_kite_mcp/oauth.py:219`.

The source now stores and rejects a mismatched resource, which is an improvement. However, SDK resource validation is disabled, and the custom guard runs only when a resource value is present. Missing-resource tokens still pass. This leaves a compatibility exception rather than strict audience enforcement.

Bind newly issued tokens to the canonical MCP resource, reject unsupported resources during authorization/token exchange, and deliberately expire or migrate legacy unbound tokens. Test absent, wrong, valid, and refreshed-resource cases. [OAuth resource binding](https://developers.openai.com/plugins/build/auth#echo-the-resource-parameter-throughout-the-oauth-flow).

## Submission prerequisites requiring owner evidence

- **Zerodha authorization:** no evidence of a third-party distribution agreement was established in this review. OpenAI restricts unofficial connectors. Provide authorization for this multi-user integration and relevant market-data use; a working API key or a non-affiliation disclaimer does not establish public-directory eligibility. This is an unresolved gate, not a finding that no agreement exists. [Third-party requirements](https://developers.openai.com/plugins/plugin-guidelines).
- **Identity and listing:** verify the publishing business, organization/project permissions, supported countries, support ownership, and complete the portal's current review fields. No portal state was inspected. [Submission requirements](https://developers.openai.com/plugins/deploy/submission).
- **Review evidence:** prepare reproducible positive and negative prompts and expected outputs, reviewer credentials, and any demo evidence requested by the portal. Include empty portfolios, disconnected/expired broker sessions, missing market-data entitlement, invalid instruments, watcher lifecycle, and trade requests.
- **Finance scope:** keep actual trade execution out of the product and avoid overstating analytics as personalized regulated advice. The read-only Kite endpoint allowlist is useful, but arbitrary script capabilities must first be contained. OpenAI prohibits investment-trade execution through plugins. [Plugin guidelines](https://developers.openai.com/plugins/plugin-guidelines#prohibited-fraudulent-deceptive-or-high-risk-services).

## What already looks aligned in the source

- SDK-based stateless Streamable HTTP at `/`; a custom path named `/mcp` is not inherently necessary.
- OAuth discovery, PKCE flow delegated to the SDK, persistent DCR clients, opaque hashed tokens, refresh rotation, and new resource-binding checks.
- New CIMD/public-client support, issuer response metadata, UserInfo, and a configurable OpenAI domain challenge route.
- Five explicit tools with all three primary safety annotations; correctness concerns are detailed above.
- Structured results for account status, profile, watcher creation, and watcher listing; an opaque-ID profile tool marked `openai/profile` with a closed output schema.
- Authenticated user identity is taken from validated access tokens; the broker gateway limits upstream access to GET/read paths.
- Public privacy/terms pages are now reachable. A graphical widget is not necessary for this text/data workflow; adding a UI is not the priority.

## Validation and limits

- `npm test`: **12 passed** across 5 files.
- `npm run typecheck`: **passed**.
- `mcp/.venv/bin/python -m pytest -ra`: **27 passed, 15 skipped**. All server integration cases were skipped because `postgresql://localhost/zap_kite_mcp_test` was unavailable. CI provisions PostgreSQL, but its current run status was not checked.
- Safe synthetic Runner checks: cross-user file read **reproduced**, cross-user file overwrite **reproduced**, inactive-user retention overrun **reproduced**. Temporary files were removed automatically.
- Public endpoint checks were unauthenticated. No login codes were requested, no accounts registered, no watcher created, and no trade attempted.
- No live ChatGPT installation, authenticated tool scan, OAuth completion, mobile acceptance, or portal submission was performed. Full compatibility remains unverified until those checks pass.
- `docs/chatgpt-support.md` is older research and no longer accurately describes the checkout or all live URLs. This report distinguishes source implementation from observed production behavior. It is placed at repository root because `docs/` is git-ignored.

## Recommended order

1. Validate the execution isolation fix and prepare the bounded `run_python` submission case, retaining the user's chosen interface and recording the accepted directory-review risk.
2. Establish third-party authorization and a stable synthetic reviewer account.
3. Correct annotations, consent, resource binding, CIMD fetching, quotas, and retention.
4. Package the server and skill in the supported OpenAI format; validate the actual archive.
5. Run the PostgreSQL-backed suite, isolation tests, and a real ChatGPT end-to-end session.
6. Deploy that reviewed version, verify the domain, scan the live tools, resolve findings, and only then submit.
