# OpenAI plugin package

The existing `plugin/` directory remains the Claude package. OpenAI-specific source
metadata and user-facing documentation live in `plugin-openai/`. Build the complete
OpenAI package before uploading; the source metadata directory alone is not a complete
installable plugin because shared assets and the skill are assembled at build time.

```sh
npm run plugin:openai:check
npm run plugin:openai:test
npm run plugin:openai:build
```

Output: `dist/slash-markets-openai-0.1.0.zip` and its `.zip.sha256` checksum.
The filename follows the version in the OpenAI manifest. The archive contains:

```text
.codex-plugin/plugin.json
.mcp.json
README.md
LICENSE
assets/icon.png
skills/slash-markets-kite-data/SKILL.md
```

The builder uses an explicit file allowlist, copies the canonical `mcp/SKILL.md`
directly, checks the complete archived payload, and produces reproducible ZIP bytes.
The existing icon is 512×512. No server code, environment files, credentials, hooks,
registered app references, or machine-specific launchers are included. Do not zip
the whole repository. Increment the OpenAI manifest version for subsequent releases.

## Format and authentication

This uses OpenAI's documented Codex compatibility format: identity and `interface`
in `.codex-plugin/plugin.json`, explicit `skills` and `mcpServers` paths, and remote
server configuration in `.mcp.json`. The runtime remains a hosted MCP service;
this package does not require code execution on the user's desktop.

Authentication is declared under the server's `extensions.com.openai.auth`: OAuth,
CIMD preference with the documented DCR fallback, and scopes `kite:read`, `openid`,
and `email`. Endpoints come from OAuth discovery. No client ID/secret or bearer token
is bundled. The endpoint is the production `https://mcp.slash.markets/`.

The portable Agent Plugins MCP schema fetched on 28 October 2026 rejects server
`extensions` with `additionalProperties: false`, while OpenAI's current examples
place OAuth configuration there. We chose the explicitly supported compatibility
format instead of altering that schema or claiming it validates these extensions.
Our repository validator checks the documented fields and our intended package
contract. It is **not** OpenAI's portal validator or an official JSON schema.

## Before portal submission

1. Finish the outstanding code review fixes and Linux sandbox verification. Deploy
   the reviewed build only when approved; building this archive does not deploy it.
2. Upload the ZIP as a plugin **with MCP**, not as skills-only. Inspect the imported
   name, Finance category, icon, four listing URLs, OAuth settings, and skill.
3. Complete publisher identity and MCP domain verification, connect the server, and
   scan its live tools. Confirm the corrected `run_python` annotations are imported.
4. Enter reviewer credentials through the secure portal form. The owner's current
   decision is to maintain the dedicated reviewer broker session manually during
   review; no demo-data mode was added. Record that maintenance procedure privately.
5. Add the required reviewer-accessible demo video URL in the portal. It is omitted
   from the ZIP until a real recording exists. Confirm availability countries in
   the portal; the package deliberately does not set a country allowlist.
6. Exercise the bundled five positive and three negative cases and record actual
   results. They are proposed reviewer scenarios, not a claim of passed live tests.
   They are imported from the package; edit and rebuild to change them.
7. Explain the retained `run_python` design and its accepted generic-executor review
   risk honestly. Package validation does not settle that policy decision.

`plugin:openai:check` only validates local payload structure, listing limits, assets,
authentication settings, and forbidden package additions. It does not verify live
URLs, OAuth login, domain ownership, publisher identity, tool scan results, or public
listing eligibility. Final portal validation remains required.

References checked on 28 October 2026:

- [Package format and MCP authentication](https://developers.openai.com/plugins/build/plugins)
- [Submission and listing fields](https://developers.openai.com/plugins/deploy/submission)
