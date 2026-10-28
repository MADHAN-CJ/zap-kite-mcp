# Script execution boundary

Script execution now requires native Linux with Bubblewrap (`bwrap`) supporting
`--disable-userns`. There is no host-Python fallback, including on macOS. Run the
MCP execution service in a Linux development VM when developing on a Mac.

Each invocation gets separate mount, user, PID, IPC, and network namespaces.
Further user namespace creation is disabled. The root filesystem starts empty;
only the Python interpreter/venv, system libraries, and `zapkite` are mounted
read-only. The service repository, `.env`, database credentials, state root,
other users' workspaces, and other jobs' sockets are not mounted.

The current user's persistent directory is mounted at `/workspace`. Its instrument
cache is private to that workspace. Script archives are written by the host under
`<state>/scripts/<user>/`, never through a path controlled by a submitted script.
The submitted source and that job's gateway socket are mounted read-only at `/job`.

The sandbox has no TCP access, including host loopback. `zapkite` communicates over
a per-job Unix socket. Its host-side bridge permits only GET requests to allowed
Kite read paths, rejects traversal and absolute URLs, enforces a per-run call budget,
and supplies its own bound run token. A submitted Authorization header cannot change
the account. The real run token is never passed into the sandbox. Existing broker
authorization and the upstream read allowlist remain in force.

The runtime is read-only inside the sandbox even when the service user owns the host
installation. A clean environment, dropped capabilities, isolated PID namespace,
parent-death handling, and process-group timeout cleanup constrain each invocation.
Hard address-space, individual-file-size, and descriptor limits are also set.
These are not complete tenant quotas: total disk use, aggregate resource accounting,
and streamed output limiting remain part of review finding 10. This boundary relies
on a maintained Linux kernel and Bubblewrap; it does not claim protection against
kernel vulnerabilities.

## Validation before release

On the Linux development/CI host:

```sh
sudo apt-get install bubblewrap
cd mcp
uv run python -m zap_kite_mcp.sandbox
uv run pytest -ra
```

The preflight executes a synthetic program using the real sandbox. It checks a
host sentinel is hidden, workspace writes work, the library is immutable, and
external network access fails. Both systemd units run this preflight with
`ExecStartPre` under the same service restrictions as normal execution. Namespace
setup failure prevents service startup; it must not be bypassed to restore service.
Use the distribution-supported Bubblewrap/user-namespace policy if AppArmor or
kernel configuration prevents startup. Do not remove namespace flags or globally
disable host protection as a workaround.

The test suite includes Linux-only checks for cross-user and host-file isolation,
runtime writes, namespace creation, host networking, persistent workspace behavior,
symlink attacks, detached-child cleanup, timeout handling, and end-to-end Unix-socket
library transport. These must pass on Linux; missing/broken Bubblewrap on Linux is
a test failure, not a skip. Four existing script-dependent server integration tests
also require Linux; the remaining auth/server tests can run on macOS with PostgreSQL.

Local macOS checks do not certify Linux isolation. The release remains pending those
tests and the target service preflight. Nothing in this change deploys automatically.
Existing `<state>/workspace/<user>/_runs` archives are not migrated or deleted by this
change; address their retention when fixing finding 9.

Implementation reference: [Bubblewrap documentation](https://github.com/containers/bubblewrap/blob/main/bwrap.xml).
