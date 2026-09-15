from datetime import UTC, datetime
from pathlib import Path

import pytest

NOW = datetime(2026, 9, 1, tzinfo=UTC)
TS = "2026-09-01T00:00:00Z"


def event(seq: int, kind: str, ts: str = TS, actor: str = "human", **fields) -> dict:
    return {"seq": seq, "ts": ts, "actor": actor, "kind": kind, **fields}


@pytest.fixture
def ctx(tmp_path: Path) -> Path:
    return tmp_path / "ctx"
