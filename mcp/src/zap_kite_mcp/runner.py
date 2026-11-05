from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .gateway import RunTokens
from .sandbox import GatewayBridge, Sandbox

_ENV_PASS = ("TZ", "LANG", "LC_ALL")
_RUN_KEEP_S = 24 * 3600


@dataclass(frozen=True)
class RunResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    truncated: bool
    timed_out: bool

    def text(self) -> str:
        head = f"exit_code={self.exit_code} duration={self.duration_ms}ms"
        if self.truncated:
            head += " TRUNCATED"
        parts = [head, "--- stdout ---\n" + (self.stdout.rstrip("\n") or "(empty)")]
        if self.stderr.strip():
            parts.append("--- stderr ---\n" + self.stderr.rstrip("\n"))
        return "\n".join(parts)


class Runner:
    def __init__(self, settings: Settings, tokens: RunTokens, gateway_url: str) -> None:
        self._settings = settings
        self._tokens = tokens
        self._gateway_url = gateway_url
        self._sandbox = Sandbox()
        settings.workspace_dir.mkdir(parents=True, exist_ok=True)
        settings.cache_dir.mkdir(parents=True, exist_ok=True)

    def workspace(self, user_id: str) -> Path:
        if not user_id or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
            for c in user_id
        ):
            raise ValueError("Invalid workspace identity")
        ws = self._settings.workspace_dir / user_id
        if ws.is_symlink():
            raise ValueError("Workspace must not be a symlink")
        ws.mkdir(parents=True, exist_ok=True)
        return ws

    def _env(self) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if k in _ENV_PASS}
        env.update(
            {
                "HOME": "/workspace",
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUNBUFFERED": "1",
                "ZAPKITE_GATEWAY_URL": "http://gateway",
                "ZAPKITE_GATEWAY_SOCKET": "/job/gateway.sock",
                "ZAPKITE_RUN_TOKEN": "scoped-to-this-job",
                "ZAPKITE_CACHE_DIR": "/workspace/.zapkite-cache",
                "ZAPKITE_CALL_BUDGET": str(self._settings.call_budget),
            }
        )
        if self._settings.risk_free_rate:
            env["ZAPKITE_RISK_FREE_RATE"] = self._settings.risk_free_rate
        for key in ("ZAPKITE_TODAY", "ZAPKITE_NOW"):
            if os.environ.get(key):
                env[key] = os.environ[key]
        return env

    def run(self, user_id: str, code: str, timeout_s: int | None = None) -> RunResult:
        """Execute `code` in a namespace sandbox with only this user's workspace.

        The run token stays in the host-side bridge and is revoked when the run ends.
        """
        s = self._settings
        timeout = max(1, min(int(timeout_s or s.script_timeout_s), s.script_max_timeout_s))
        ws = self.workspace(user_id)
        self._sandbox.check_available()
        # Never read/write host-side script files through a user-controlled workspace.
        runs = s.state_dir / "scripts" / user_id
        runs.mkdir(parents=True, exist_ok=True)
        _prune(runs)
        script = runs / f"run_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.py"
        script.write_text(code, encoding="utf-8")
        token = self._tokens.issue(user_id, ttl_s=timeout + 30)
        started = time.monotonic()
        timed_out = False
        try:
            with tempfile.TemporaryDirectory(prefix="kite-job-", dir="/tmp") as temp:
                job = Path(temp)
                (job / "code.py").write_text(code, encoding="utf-8")
                with GatewayBridge(job / "gateway.sock", self._gateway_url, token, s.call_budget):
                    command = self._sandbox.command(ws, job, self._env())
                    proc = subprocess.Popen(
                        command,
                        env={"PATH": "/usr/bin:/bin"},
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        stdin=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                    try:
                        out_b, err_b = proc.communicate(timeout=timeout)
                    except subprocess.TimeoutExpired:
                        timed_out = True
                        with contextlib.suppress(ProcessLookupError):
                            os.killpg(proc.pid, signal.SIGKILL)
                        out_b, err_b = proc.communicate()
                    finally:
                        if proc.poll() is None:
                            with contextlib.suppress(ProcessLookupError):
                                os.killpg(proc.pid, signal.SIGKILL)
                            proc.wait()
        finally:
            self._tokens.revoke(token)
        duration_ms = int((time.monotonic() - started) * 1000)
        stdout, t1 = _cap(out_b.decode("utf-8", "replace"), s.max_output_bytes)
        stderr, t2 = _cap(err_b.decode("utf-8", "replace"), s.max_output_bytes // 2)
        if timed_out:
            note = (
                f"[timed out after {timeout}s and was killed. Fetch less, or pass a larger "
                f"timeout_seconds (max {s.script_max_timeout_s}).]"
            )
            stderr = f"{stderr}\n{note}" if stderr else note
        return RunResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=-9 if timed_out else proc.returncode,
            duration_ms=duration_ms,
            truncated=t1 or t2,
            timed_out=timed_out,
        )


def _cap(text: str, limit: int) -> tuple[str, bool]:
    data = text.encode("utf-8", "replace")
    if len(data) <= limit:
        return text, False
    head = data[:limit].decode("utf-8", "ignore")
    note = (
        f"[output truncated: {len(data) - limit} bytes omitted. Print less; save large data to a "
        "file in the workspace and print a summary.]"
    )
    return f"{head}\n{note}", True


def _prune(runs: Path) -> None:
    cutoff = time.time() - _RUN_KEEP_S
    for f in runs.glob("run_*.py"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass
