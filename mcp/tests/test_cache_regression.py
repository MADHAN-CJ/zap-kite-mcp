from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from zapkite import client, instruments


def test_parallel_cache_builds_do_not_share_temporary_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    barrier = Barrier(2)
    original = sqlite3.connect

    def connect(path: str) -> sqlite3.Connection:
        connection = original(path)
        barrier.wait(timeout=5)
        return connection

    monkeypatch.setattr(client, "instruments_csv", lambda: "")
    monkeypatch.setattr(sqlite3, "connect", connect)
    path = tmp_path / "instruments.sqlite3"
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(instruments._build, str(path)) for _ in range(2)]
        for job in jobs:
            job.result(timeout=10)
    with original(path) as connection:
        assert connection.execute("select count(*) from instruments").fetchone() == (0,)
    assert not list(tmp_path.glob("*.tmp"))
