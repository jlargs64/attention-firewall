import json
from pathlib import Path

import pytest
from conftest import event

from attention_firewall.ledger import (
    ACTOR_RE,
    LOG_NAME,
    LedgerError,
    NotFound,
    append_event,
    read_events,
    resolve_context,
    validate,
)

CREATED = event(1, "context_created", slot_cap=3, stall_after_days=7)
MISSION = event(2, "mission_created", slug="a", title="A")
FROM_TO = {"from": "active", "to": "done"}


def write_lines(ctx: Path, *lines: str) -> Path:
    ctx.mkdir(parents=True, exist_ok=True)
    log = ctx / LOG_NAME
    log.write_bytes("".join(line + "\n" for line in lines).encode())
    return log


def test_first_append_creates_log_with_one_line(ctx: Path) -> None:
    ctx.mkdir()
    append_event(ctx, CREATED)
    lines = (ctx / LOG_NAME).read_bytes().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == CREATED


def test_append_preserves_prior_bytes(ctx: Path) -> None:
    ctx.mkdir()
    append_event(ctx, CREATED)
    before = (ctx / LOG_NAME).read_bytes()
    append_event(ctx, event(2, "mission_created", slug="a", title="A"))
    after = (ctx / LOG_NAME).read_bytes()
    assert after.startswith(before)
    assert after.count(b"\n") == 2


def test_read_returns_contiguous_seq(ctx: Path) -> None:
    write_lines(ctx, json.dumps(CREATED), json.dumps(MISSION))
    assert [e["seq"] for e in read_events(ctx)] == [1, 2]


def test_seq_gap_names_line(ctx: Path) -> None:
    write_lines(ctx, json.dumps(CREATED), json.dumps({**MISSION, "seq": 3}))
    with pytest.raises(LedgerError) as exc:
        read_events(ctx)
    assert exc.value.line_no == 2


def test_truncated_line_names_line(ctx: Path) -> None:
    write_lines(ctx, json.dumps(CREATED), '{"seq": 2, "kind": "item_created"')
    with pytest.raises(LedgerError, match="line 2") as exc:
        read_events(ctx)
    assert exc.value.line_no == 2


def test_unknown_kind_names_line(ctx: Path) -> None:
    write_lines(ctx, json.dumps(CREATED), json.dumps(event(2, "teleport")))
    with pytest.raises(LedgerError, match="teleport") as exc:
        read_events(ctx)
    assert exc.value.line_no == 2


@pytest.mark.parametrize(
    "bad",
    [
        {**CREATED, "slot_cap": "3"},
        {**CREATED, "slot_cap": True},
        {k: v for k, v in CREATED.items() if k != "ts"},
        {**CREATED, "ts": "yesterday"},
        {**CREATED, "actor": "robot"},
        event(1, "item_transitioned", id=1, edge="pull", **{"from": "holding", "to": "orbit"}),
        event(1, "item_transitioned", id=1, edge="x", human_allowed="yes", **FROM_TO),
        [1, 2],
    ],
)
def test_validate_rejects_bad_shapes(bad: object) -> None:
    with pytest.raises(LedgerError):
        validate(bad, 1)


def test_missing_context_is_not_found(ctx: Path) -> None:
    with pytest.raises(NotFound):
        read_events(ctx)


def test_context_option_beats_env_beats_xdg(tmp_path: Path) -> None:
    env = {"FW_CONTEXT": "/from-env", "XDG_DATA_HOME": str(tmp_path)}
    assert resolve_context("/from-opt", env) == Path("/from-opt")
    assert resolve_context(None, env) == Path("/from-env")
    assert resolve_context(None, {"XDG_DATA_HOME": str(tmp_path)}) == tmp_path / "fw"
    assert resolve_context(None, {}) == Path.home() / ".local" / "share" / "fw"


@pytest.mark.parametrize("actor", ["human", "system", "agent:claude", "agent:fw-intake.v2"])
def test_actor_pattern_accepts(actor: str) -> None:
    assert ACTOR_RE.match(actor)


@pytest.mark.parametrize("actor", ["robot", "agent:", "agent:Claude", "agent:a b", "Human"])
def test_actor_pattern_rejects(actor: str) -> None:
    assert not ACTOR_RE.match(actor)
