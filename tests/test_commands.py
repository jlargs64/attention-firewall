import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import NOW

from attention_firewall import commands
from attention_firewall.ledger import LOG_NAME, NotFound, Refusal


def log_bytes(ctx: Path) -> bytes:
    return (ctx / LOG_NAME).read_bytes()


@pytest.fixture
def seeded(ctx: Path) -> Path:
    commands.init(ctx, "human", NOW)
    commands.mission_add(ctx, "human", NOW, "ship-fw", "Ship")
    commands.add(ctx, "human", NOW, "one", "ship-fw")
    commands.add(ctx, "human", NOW, "two")
    commands.add(ctx, "human", NOW, "three", "ship-fw")
    return ctx


def test_init_creates_directory_and_first_line(ctx: Path) -> None:
    result = commands.init(ctx, "human", NOW, slots=2, stall_days=10)
    lines = log_bytes(ctx).splitlines()
    assert len(lines) == 1
    first = json.loads(lines[0])
    assert first["kind"] == "context_created"
    assert (first["slot_cap"], first["stall_after_days"]) == (2, 10)
    assert result["event"] == first


def test_init_twice_is_refused(ctx: Path) -> None:
    commands.init(ctx, "human", NOW)
    before = log_bytes(ctx)
    with pytest.raises(Refusal, match=str(ctx)):
        commands.init(ctx, "human", NOW)
    assert log_bytes(ctx) == before


def test_command_before_init_is_not_found(ctx: Path) -> None:
    with pytest.raises(NotFound, match="not initialized"):
        commands.status(ctx, NOW)


def test_success_appends_exactly_one_line(seeded: Path) -> None:
    before = log_bytes(seeded)
    result = commands.transition(seeded, "human", NOW, "pull", 1, until="2026-10-01")
    after = log_bytes(seeded)
    assert after.startswith(before)
    assert after.count(b"\n") == before.count(b"\n") + 1
    assert result["event"]["until"] == "2026-10-01"
    assert "human_allowed" not in result["event"]


def test_refused_transition_leaves_log_byte_identical(seeded: Path) -> None:
    before = log_bytes(seeded)
    with pytest.raises(Refusal):
        commands.transition(seeded, "human", NOW, "done", 1)
    with pytest.raises(Refusal):
        commands.transition(seeded, "human", NOW, "pull", 2, until="2026-10-01")
    with pytest.raises(NotFound):
        commands.transition(seeded, "human", NOW, "pull", 9, until="2026-10-01")
    assert log_bytes(seeded) == before


def test_agent_pull_records_permission(seeded: Path) -> None:
    result = commands.transition(
        seeded, "agent:claude", NOW, "pull", 1, until="2026-10-01", human_allowed=True
    )
    assert result["event"]["actor"] == "agent:claude"
    assert result["event"]["human_allowed"] is True


def test_duplicate_mission_refused(seeded: Path) -> None:
    before = log_bytes(seeded)
    with pytest.raises(Refusal):
        commands.mission_add(seeded, "human", NOW, "ship-fw")
    assert log_bytes(seeded) == before


def test_add_with_unknown_mission(seeded: Path) -> None:
    before = log_bytes(seeded)
    with pytest.raises(NotFound):
        commands.add(seeded, "human", NOW, "x", "nope")
    assert log_bytes(seeded) == before


def test_map_then_mission_list_counts(seeded: Path) -> None:
    commands.map_item(seeded, "human", NOW, 2, "ship-fw")
    commands.transition(seeded, "human", NOW, "pull", 1, until="2026-10-01")
    result = commands.mission_list(seeded, NOW)
    assert result["missions"] == [
        {"slug": "ship-fw", "title": "Ship", "items": {"active": 1, "holding": 2}}
    ]


def test_map_terminal_item_refused(seeded: Path) -> None:
    commands.transition(seeded, "human", NOW, "drop", 1)
    with pytest.raises(Refusal):
        commands.map_item(seeded, "human", NOW, 1, "ship-fw")


def test_stall_pass_appends_before_command(seeded: Path) -> None:
    commands.transition(seeded, "human", NOW, "pull", 1, until="2026-10-01")
    later = datetime(2026, 9, 20, tzinfo=UTC)
    result = commands.status(seeded, later)
    assert result["active"][0]["state"] == "stalled"
    stall = commands.log(seeded, later, item=1)["events"][-1]
    assert (stall["edge"], stall["actor"]) == ("stall", "system")
    assert stall["ts"] == "2026-09-20T00:00:00Z"


def test_log_filters_and_limits(seeded: Path) -> None:
    events = commands.log(seeded, NOW, item=1)["events"]
    assert [e["id"] for e in events] == [1]
    assert len(commands.log(seeded, NOW, limit=2)["events"]) == 2
    seqs = [e["seq"] for e in commands.log(seeded, NOW)["events"]]
    assert seqs == sorted(seqs)


# --- export -----------------------------------------------------------------


def test_export_jsonl_is_byte_identical(seeded: Path, tmp_path: Path) -> None:
    out = tmp_path / "fw.jsonl"
    before = log_bytes(seeded)
    commands.export(seeded, "jsonl", out)
    assert out.read_bytes() == before
    assert log_bytes(seeded) == before


def test_export_csv_has_header_and_one_row_per_item(seeded: Path, tmp_path: Path) -> None:
    out = tmp_path / "fw.csv"
    before = log_bytes(seeded)
    commands.export(seeded, "csv", out)
    with out.open(newline="") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == commands.CSV_COLUMNS
    assert len(rows) == 4
    assert rows[1][:4] == ["1", "one", "ship-fw", "holding"]
    assert log_bytes(seeded) == before


# --- config -----------------------------------------------------------------


def test_config_raise_cap(seeded: Path) -> None:
    commands.config_set(seeded, "human", NOW, "slot-cap", 4)
    assert commands.status(seeded, NOW)["slot_cap"] == 4


def test_config_lower_cap_below_occupied_shows_excess(seeded: Path) -> None:
    commands.transition(seeded, "human", NOW, "pull", 1, until="2026-10-01")
    commands.transition(seeded, "human", NOW, "pull", 3, until="2026-10-01")
    commands.config_set(seeded, "human", NOW, "slot-cap", 1)
    result = commands.status(seeded, NOW)
    assert (result["slots_used"], result["slot_cap"], result["slots_free"]) == (2, 1, 0)


def test_config_stall_days(seeded: Path) -> None:
    event = commands.config_set(seeded, "human", NOW, "stall-days", 30)["event"]
    assert (event["key"], event["value"]) == ("stall_after_days", 30)
