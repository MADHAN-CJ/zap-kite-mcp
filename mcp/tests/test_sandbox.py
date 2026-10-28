from __future__ import annotations

import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import httpx
import pytest

from zap_kite_mcp.config import Settings
from zap_kite_mcp.gateway import RunTokens
from zap_kite_mcp.runner import Runner
from zap_kite_mcp.sandbox import GatewayBridge, Sandbox, SandboxUnavailable, allowed_gateway_target


@pytest.fixture
def socket_dir() -> Iterator[Path]:
    # AF_UNIX paths are limited to roughly 100 bytes, including pytest's base path.
    with tempfile.TemporaryDirectory(prefix="kite-test-", dir="/tmp") as directory:
        yield Path(directory)


@pytest.mark.parametrize(
    "path",
    [
        "/authorize",
        "/internal/sweep",
        "https://evil.example/kite/orders",
        "/kite/orders/../../userinfo",
        "/kite/orders/%2e%2e/userinfo",
        "/kite/orders/%252e%252e/userinfo",
        "//evil.example/kite/orders",
        "/kite/orders/../orders",
        "/kite/orders\\..\\userinfo",
    ],
)
def test_bridge_rejects_non_read_targets(path: str) -> None:
    assert not allowed_gateway_target(path)


def test_bridge_binds_identity_and_budget(socket_dir: Path) -> None:
    calls: list[httpx.Request] = []

    def upstream(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"data": "synthetic"})

    bridge = GatewayBridge(socket_dir / "gateway.sock", "http://localhost:8019", "bound-token", 1)
    bridge.client.close()
    bridge.client = httpx.Client(transport=httpx.MockTransport(upstream))
    with bridge, httpx.Client(transport=httpx.HTTPTransport(uds=str(bridge.path))) as client:
        response = client.get(
            "http://gateway/kite/quote?i=NSE:TCS", headers={"Authorization": "Bearer other-user"}
        )
        assert response.status_code == 200
        assert calls[0].headers["authorization"] == "Bearer bound-token"
        assert client.get("http://gateway/kite/orders").status_code == 429
        assert client.post("http://gateway/kite/orders").status_code == 501
        assert client.get("http://gateway/internal/sweep").status_code == 403
        assert len(calls) == 1


def test_missing_sandbox_never_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("zap_kite_mcp.sandbox.shutil.which", lambda _: None)
    with pytest.raises(SandboxUnavailable):
        Sandbox().check_available()


def test_workspace_rejects_traversal_and_symlinks(tmp_path: Path) -> None:
    from types import SimpleNamespace

    settings = cast(
        Settings, SimpleNamespace(workspace_dir=tmp_path / "work", cache_dir=tmp_path / "cache")
    )
    runner = Runner(settings, RunTokens(), "http://localhost:1")
    for identity in ("../other", "", "/tmp", "a/b"):
        with pytest.raises(ValueError):
            runner.workspace(identity)
    (settings.workspace_dir / "linked").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        runner.workspace("linked")


@pytest.mark.skipif(sys.platform != "linux", reason="Linux kernel namespace test")
def test_real_sandbox_isolation_and_gateway(tmp_path: Path) -> None:
    from types import SimpleNamespace

    settings = cast(
        Settings,
        SimpleNamespace(
            workspace_dir=tmp_path / "workspace",
            cache_dir=tmp_path / "cache",
            state_dir=tmp_path,
            script_timeout_s=8,
            script_max_timeout_s=8,
            max_output_bytes=4096,
            call_budget=3,
            risk_free_rate="",
        ),
    )
    runner = Runner(settings, RunTokens(), "http://localhost:1")
    other = runner.workspace("other") / "secret"
    other.write_text("synthetic-only")
    secret = tmp_path / "server.env"
    secret.write_text("synthetic-only")
    code = f"""
from pathlib import Path
import socket, zapkite, ctypes
assert ctypes.CDLL(None, use_errno=True).unshare(0x10000000) == -1
assert not Path({str(secret)!r}).exists()
assert not Path({str(other)!r}).exists()
assert not Path('../other/secret').exists()
try:
    Path(zapkite.__file__).write_text('tampered')
    raise AssertionError('runtime writable')
except OSError: pass
try:
    socket.create_connection(('127.0.0.1',8019),timeout=1)
    raise AssertionError('host TCP available')
except OSError: pass
Path('saved').write_text('persisted')
print('isolated')
"""
    result = runner.run("user", code)
    assert result.exit_code == 0, result.text()
    assert "isolated" in result.stdout
    again = runner.run("user", "from pathlib import Path;print(Path('saved').read_text())")
    assert again.exit_code == 0, again.text()
    assert "persisted" in again.stdout
    assert other.read_text() == "synthetic-only"
    assert secret.read_text() == "synthetic-only"
    # A persisted symlink may not redirect server-side script storage/pruning.
    result = runner.run("user", "from pathlib import Path;Path('_runs').symlink_to('/job')")
    assert result.exit_code == 0, result.text()
    assert runner.run("user", "print(1)").exit_code == 0
    # A detached child must not survive its run's PID namespace.
    child = (
        "import time;from pathlib import Path;time.sleep(2);"
        "Path('/workspace/escaped').write_text('bad')"
    )
    parent = (
        "import subprocess,sys;subprocess.Popen([sys.executable,'-c',"
        + repr(child)
        + "],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)"
    )
    assert runner.run("user", parent).exit_code == 0
    result = runner.run(
        "user",
        "import time;from pathlib import Path;time.sleep(3);assert not Path('escaped').exists()",
    )
    assert result.exit_code == 0, result.text()
    result = runner.run("user", "import time;time.sleep(10)", 1)
    assert result.timed_out


@pytest.mark.skipif(sys.platform != "linux", reason="Linux kernel namespace test")
def test_real_socket_transport(socket_dir: Path) -> None:
    workspace, job = socket_dir / "workspace", socket_dir / "job"
    workspace.mkdir()
    job.mkdir()
    (job / "code.py").write_text("import zapkite as z; print(z.kite_get('/user/profile'))")
    bridge = GatewayBridge(job / "gateway.sock", "http://localhost:1", "bound", 3)
    bridge.client.close()
    bridge.client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"data": {"user_id": "synthetic"}})
        )
    )
    with bridge:
        result = subprocess.run(
            Sandbox().command(
                workspace,
                job,
                {
                    "HOME": "/workspace",
                    "ZAPKITE_GATEWAY_URL": "http://gateway",
                    "ZAPKITE_RUN_TOKEN": "scoped",
                    "ZAPKITE_GATEWAY_SOCKET": "/job/gateway.sock",
                },
            ),
            capture_output=True,
            text=True,
            timeout=15,
        )
    assert result.returncode == 0, result.stderr
    assert "synthetic" in result.stdout


def test_bridge_preserves_endpoint_timeouts(socket_dir: Path) -> None:
    seen: list[float] = []

    def upstream(request: httpx.Request) -> httpx.Response:
        seen.append(request.extensions["timeout"]["read"])
        return httpx.Response(200, json={"data": []})

    bridge = GatewayBridge(socket_dir / "timeouts.sock", "http://localhost:1", "bound", 3)
    bridge.client.close()
    bridge.client = httpx.Client(transport=httpx.MockTransport(upstream))
    with bridge, httpx.Client(transport=httpx.HTTPTransport(uds=str(bridge.path))) as client:
        for path in ("instruments", "instruments/historical/1/day", "quote"):
            assert client.get("http://gateway/kite/" + path).status_code == 200
    assert seen == [125, 35, 20]
