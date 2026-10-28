"""Linux execution boundary. No host execution fallback is permitted."""

from __future__ import annotations

import shutil
import socketserver
import sys
import threading
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from types import TracebackType
from urllib.parse import unquote, urlsplit

import httpx

import zapkite
from zapkite.http import _timeout_for

from .gateway import _allowed


class SandboxUnavailable(RuntimeError):
    pass


class Sandbox:
    def check_available(self) -> str:
        binary = shutil.which("bwrap") if sys.platform == "linux" else None
        if not binary:
            raise SandboxUnavailable(
                "Script execution requires Linux and bubblewrap; host execution is disabled."
            )
        return binary

    def command(self, workspace: Path, job: Path, env: dict[str, str]) -> list[str]:
        binary = self.check_available()
        # Mount only interpreter trees and the public data library, never the repository,
        # service HOME, environment file, state root, or another customer's directory.
        roots = {Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve()}
        if any(root == Path("/") or workspace.is_relative_to(root) for root in roots):
            raise SandboxUnavailable("Interpreter prefix overlaps customer storage")
        command = [
            binary,
            "--unshare-all",
            "--unshare-user",
            "--disable-userns",
            "--die-with-parent",
            "--new-session",
            "--cap-drop",
            "ALL",
            "--clearenv",
        ]
        for root in sorted(roots):
            command += ["--ro-bind", str(root), str(root)]
        for directory in ("/lib", "/lib64", "/usr/lib"):
            if Path(directory).exists():
                command += ["--ro-bind", directory, directory]
        library = Path(zapkite.__file__).resolve().parent
        command += [
            "--ro-bind",
            str(library),
            "/library/zapkite",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
            "--bind",
            str(workspace.resolve()),
            "/workspace",
            "--ro-bind",
            str(job.resolve()),
            "/job",
            "--chdir",
            "/workspace",
            "--remount-ro",
            "/",
        ]
        for key, value in env.items():
            command += ["--setenv", key, value]
        # Hard resource limits cannot be raised by the submitted program.
        bootstrap = (
            "import resource,runpy,sys;"
            "resource.setrlimit(resource.RLIMIT_AS,(536870912,536870912));"
            "resource.setrlimit(resource.RLIMIT_FSIZE,(67108864,67108864));"
            "resource.setrlimit(resource.RLIMIT_NOFILE,(128,128));"
            "sys.path.insert(0,'/library');runpy.run_path('/job/code.py',run_name='__main__')"
        )
        return [*command, "--", sys.executable, "-I", "-u", "-c", bootstrap]


def allowed_gateway_target(target: str) -> bool:
    parsed = urlsplit(target)
    path = unquote(parsed.path)
    return (
        not parsed.scheme
        and not parsed.netloc
        and not parsed.fragment
        and path.startswith("/kite/")
        and "\\" not in path
        and "%" not in path
        and all(part not in (".", "..", "") for part in path[1:].split("/"))
        and _allowed(path.removeprefix("/kite/"))
    )


class _BridgeServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    block_on_close = False


class GatewayBridge:
    """A per-job socket, bound to one run token, with no general-purpose proxying.

    Only this socket is mounted in the sandbox. The process cannot reach TCP,
    public OAuth endpoints, the database, or other jobs' gateway sockets.
    """

    def __init__(self, path: Path, gateway_url: str, token: str, budget: int) -> None:
        self.path = path
        self.gateway_url = gateway_url.rstrip("/")
        self.token = token
        self.remaining = budget
        self.lock = threading.Lock()
        self.client = httpx.Client(trust_env=False, follow_redirects=False, timeout=10)
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def setup(self) -> None:
                self.request.settimeout(2)
                super().setup()

            def log_message(self, format: str, *args: object) -> None:
                pass

            def do_GET(self) -> None:
                if not allowed_gateway_target(self.path):
                    self.send_error(403, "Only Kite read endpoints are allowed")
                    return
                with bridge.lock:
                    if bridge.remaining <= 0:
                        self.send_error(429, "Run request budget exceeded")
                        return
                    bridge.remaining -= 1
                try:
                    response = bridge.client.get(
                        bridge.gateway_url + self.path,
                        headers={"Authorization": f"Bearer {bridge.token}"},
                        timeout=_timeout_for(urlsplit(self.path).path.removeprefix("/kite/"), 15)
                        + 5,
                    )
                except httpx.HTTPError:
                    self.send_error(502, "Kite gateway unavailable")
                    return
                self.send_response(response.status_code)
                self.send_header(
                    "Content-Type", response.headers.get("content-type", "application/json")
                )
                self.send_header("Content-Length", str(len(response.content)))
                self.end_headers()
                self.wfile.write(response.content)

        self.server = _BridgeServer(str(path), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> GatewayBridge:
        self.thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.client.close()


def preflight() -> None:
    """Exercise the actual namespace policy under the service's systemd restrictions."""
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory(prefix="kite-preflight-") as temporary:
        root = Path(temporary)
        workspace, job = root / "workspace", root / "job"
        workspace.mkdir()
        job.mkdir()
        sentinel = root / "host-secret"
        sentinel.write_text("synthetic-only")
        script = (
            "import pathlib,socket,zapkite\n"
            f"assert not pathlib.Path({str(sentinel)!r}).exists()\n"
            "p=pathlib.Path('/workspace/probe');p.write_text('ok');p.unlink()\n"
            "try:\n"
            " pathlib.Path(zapkite.__file__).write_text('changed')\n"
            " raise AssertionError('runtime is writable')\n"
            "except OSError: pass\n"
            "try:\n"
            " socket.create_connection(('1.1.1.1',443),timeout=1)\n"
            " raise AssertionError('network is reachable')\n"
            "except OSError: pass\n"
            "print('sandbox preflight passed')\n"
        )
        (job / "code.py").write_text(script)
        command = Sandbox().command(workspace, job, {"HOME": "/workspace"})
        subprocess.run(command, check=True, timeout=15, env={"PATH": "/usr/bin:/bin"})


if __name__ == "__main__":
    preflight()
