from datetime import UTC, datetime

import pytest
from conftest import NOW, event

from attention_firewall.graph import EDGES, Snapshot, check, fold, stall_pass, status
from attention_firewall.ledger import LedgerError, NotFound, Refusal


def moved(seq: int, item: int, edge: str, ts: str = "2026-09-01T00:00:00Z", **extra) -> dict:
    src, dst = EDGES[edge]
    fields = {"id": item, "edge": edge, "from": min(src), "to": dst, **extra}
    return event(seq, "item_transitioned", ts, **fields)


def base(cap: int = 3) -> list[dict]:
    return [
        event(1, "context_created", slot_cap=cap, stall_after_days=7),
        event(2, "mission_created", slug="ship-fw", title="Ship"),
        event(3, "item_created", id=1, title="one", mission="ship-fw"),
        event(4, "item_created", id=2, title="two", mission=None),
        event(5, "item_created", id=3, title="three", mission="ship-fw"),
        event(6, "item_created", id=4, title="four", mission="ship-fw"),
    ]


def full_column() -> Snapshot:
    """Items 1, 2, 3 occupy all three slots (2 is mapped first); 4 is holding."""
    events = base() + [
        event(7, "item_mapped", id=2, mission="ship-fw"),
        moved(8, 1, "pull", until="2026-10-01"),
        moved(9, 2, "pull", until="2026-09-20"),
        moved(10, 3, "pull", until="2026-11-15"),
    ]
    return fold(events)


def refused(snap: Snapshot, item: int, edge: str, actor: str = "human", **kw) -> str:
    result = check(snap, item, edge, actor, **kw)
    assert isinstance(result, Refusal)
    return str(result)


# --- fold -------------------------------------------------------------------


def test_fold_states_missions_and_config() -> None:
    snap = fold(
        base()
        + [
            moved(7, 1, "pull", until="2026-10-01"),
            moved(8, 1, "done"),
            event(9, "config_changed", key="slot_cap", value=5),
        ]
    )
    assert snap.missions == {"ship-fw": "Ship"}
    assert snap.config == {"slot_cap": 5, "stall_after_days": 7}
    assert snap.item(1).state == "done"
    assert snap.item(1).until == "2026-10-01"
    assert snap.item(2).state == "holding"
    assert snap.item(2).mission is None


def test_fold_counts_overrides_and_tracks_last_ts() -> None:
    snap = fold(base() + [moved(7, 1, "override", ts="2026-09-05T00:00:00Z", until="2026-10-01")])
    assert snap.item(1).overrides == 1
    assert snap.item(1).last_ts == "2026-09-05T00:00:00Z"


def test_fold_rejects_event_for_unknown_item() -> None:
    with pytest.raises(LedgerError, match="line 7"):
        fold(base() + [event(7, "item_mapped", id=99, mission="ship-fw")])


def test_unknown_item_is_not_found() -> None:
    with pytest.raises(NotFound):
        check(fold(base()), 99, "done", "human")


# --- Item states and edges --------------------------------------------------


def test_valid_edge_done_from_active() -> None:
    snap = fold(base() + [moved(7, 1, "pull", until="2026-10-01")])
    assert check(snap, 1, "done", "human") is None


def test_invalid_edge_done_from_holding() -> None:
    assert "not permitted from holding" in refused(fold(base()), 1, "done")


@pytest.mark.parametrize("final", ["done", "drop"])
def test_terminal_state_refuses_everything(final: str) -> None:
    snap = fold(base() + [moved(7, 1, "pull", until="2026-10-01"), moved(8, 1, final)])
    for edge in EDGES:
        assert isinstance(check(snap, 1, edge, "human"), Refusal)


# --- Slot cap on pull -------------------------------------------------------


def test_pull_into_free_slot() -> None:
    snap = fold(base() + [moved(7, 1, "pull", until="2026-10-01"), moved(8, 3, "pull")])
    assert len(snap.occupied()) == 2
    assert check(snap, 4, "pull", "human") is None


def test_pull_into_full_column() -> None:
    assert "column is full (3/3" in refused(full_column(), 4, "pull")


def test_pull_without_mission() -> None:
    assert "not mapped to a mission" in refused(fold(base()), 2, "pull")


def test_wait_frees_a_slot() -> None:
    snap = full_column()
    assert check(snap, 1, "wait", "human") is None
    snap = fold(base() + [moved(7, 1, "pull"), moved(8, 1, "wait")])
    assert snap.item(1).state == "waiting"
    assert snap.occupied() == []


def test_resume_from_waiting_into_full_column() -> None:
    events = base() + [
        event(7, "item_mapped", id=2, mission="ship-fw"),
        moved(8, 4, "pull"),
        moved(9, 4, "wait"),
        moved(10, 1, "pull"),
        moved(11, 2, "pull"),
        moved(12, 3, "pull"),
    ]
    snap = fold(events)
    assert "column is full" in refused(snap, 4, "resume")


def test_resume_from_stalled_ignores_cap() -> None:
    snap = fold(base() + [moved(7, 1, "pull"), moved(8, 3, "pull"), moved(9, 4, "pull")])
    snap.item(1).state = "stalled"
    assert check(snap, 1, "resume", "human") is None


# --- Pull is a human decision -----------------------------------------------


def test_agent_pull_refused() -> None:
    assert "requires a human" in refused(fold(base()), 1, "pull", actor="agent:claude")


def test_agent_pull_with_permission() -> None:
    assert check(fold(base()), 1, "pull", "agent:claude", human_allowed=True) is None


def test_agent_drop_permitted() -> None:
    assert check(fold(base()), 1, "drop", "agent:claude") is None


# --- Override bypasses the cap and is limited -------------------------------


def test_override_into_full_column() -> None:
    snap = full_column()
    assert check(snap, 4, "override", "human") is None
    snap = fold(base() + [moved(7, 4, "override")])
    assert snap.item(4).state == "active"


def test_override_without_mission() -> None:
    assert "not mapped" in refused(fold(base()), 2, "override")


def locked() -> Snapshot:
    return fold(base() + [moved(7 + i, 4, "override") for i in range(3)])


def test_third_override_locks_the_item() -> None:
    assert "only delegate or drop remain" in refused(locked(), 4, "done")


@pytest.mark.parametrize("edge", ["drop", "delegate"])
def test_locked_item_can_be_dropped_or_delegated(edge: str) -> None:
    assert check(locked(), 4, edge, "human") is None


# --- Stall by timestamp arithmetic -----------------------------------------


def active_since_sept_1(*ids: int) -> Snapshot:
    return fold(base() + [moved(7 + n, i, "pull") for n, i in enumerate(ids)])


def at(day: int) -> datetime:
    return datetime(2026, 9, day, tzinfo=UTC)


def test_stall_after_threshold() -> None:
    events = stall_pass(active_since_sept_1(1), at(9), 7)
    assert [(e["id"], e["edge"], e["actor"], e["ts"]) for e in events] == [
        (1, "stall", "system", "2026-09-09T00:00:00Z")
    ]


def test_not_yet_stalled() -> None:
    assert stall_pass(active_since_sept_1(1), at(7), 7) == []


def test_long_absence_stalls_both() -> None:
    assert [e["id"] for e in stall_pass(active_since_sept_1(1, 3), at(20), 7)] == [1, 3]


def test_activity_resets_the_clock() -> None:
    snap = active_since_sept_1(1)
    snap.item(1).last_ts = "2026-09-06T00:00:00Z"
    assert stall_pass(snap, at(10), 7) == []


def test_stalled_item_is_not_stalled_twice() -> None:
    snap = active_since_sept_1(1)
    snap.item(1).state = "stalled"
    assert stall_pass(snap, at(30), 7) == []


# --- Status -----------------------------------------------------------------


def test_status_free_slot() -> None:
    result = status(active_since_sept_1(1, 3), NOW)
    assert result["slots_used"] == 2
    assert result["slots_free"] == 1
    assert result["next_open"] == "2026-09-01"
    assert [i["id"] for i in result["holding"]] == [2, 4]


def test_status_full_column_with_dates() -> None:
    result = status(full_column(), NOW)
    assert result["slots_free"] == 0
    assert result["next_open"] == "2026-09-20"
    assert result["holding"][0]["id"] == 4


def test_status_overridden_column() -> None:
    snap = fold(
        base()
        + [
            event(7, "item_mapped", id=2, mission="ship-fw"),
            moved(8, 1, "pull"),
            moved(9, 2, "pull"),
            moved(10, 3, "pull"),
            moved(11, 4, "override"),
        ]
    )
    result = status(snap, NOW)
    assert (result["slots_used"], result["slot_cap"], result["slots_free"]) == (4, 3, 0)
    assert result["next_open"] is None


def test_status_counts_waiting_and_delegated() -> None:
    snap = fold(base() + [moved(7, 1, "pull"), moved(8, 1, "wait"), moved(9, 3, "delegate")])
    result = status(snap, NOW)
    assert (result["waiting"], result["delegated"]) == (1, 1)
