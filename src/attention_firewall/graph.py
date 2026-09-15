"""Pure state rules: fold events into a snapshot, check edges, stall, status.

Nothing here touches the filesystem or the clock. Time arrives as `now`.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .ledger import LedgerError, NotFound, Refusal, fmt_ts, parse_ts

TERMINAL = frozenset({"dropped", "done"})
OCCUPYING = frozenset({"active", "stalled"})
HUMAN_ONLY = frozenset({"pull", "override", "resume"})
DATED = HUMAN_ONLY  # edges whose event carries `until`
LOCK_ESCAPES = frozenset({"delegate", "drop"})
MAX_OVERRIDES = 2

# edge -> (allowed from, to). Mirrors the bandwidth-graph spec table exactly.
EDGES: dict[str, tuple[frozenset[str], str]] = {
    "pull": (frozenset({"holding"}), "active"),
    "override": (frozenset({"holding"}), "active"),
    "done": (frozenset({"active", "stalled", "delegated"}), "done"),
    "drop": (frozenset({"holding", "active", "stalled", "waiting", "delegated"}), "dropped"),
    "delegate": (frozenset({"holding", "active", "stalled", "waiting"}), "delegated"),
    "wait": (frozenset({"active", "stalled"}), "waiting"),
    "resume": (frozenset({"waiting", "stalled"}), "active"),
    "stall": (frozenset({"active"}), "stalled"),
}


@dataclass
class Item:
    id: int
    title: str
    mission: str | None
    created: str
    last_ts: str
    state: str = "holding"
    until: str | None = None
    overrides: int = 0

    def row(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "mission": self.mission,
            "state": self.state,
            "until": self.until,
        }


@dataclass
class Snapshot:
    config: dict[str, int] = field(default_factory=dict)
    missions: dict[str, str] = field(default_factory=dict)
    items: dict[int, Item] = field(default_factory=dict)

    def item(self, item_id: int) -> Item:
        try:
            return self.items[item_id]
        except KeyError:
            raise NotFound(f"item {item_id} not found") from None

    def occupied(self) -> list[Item]:
        return [i for i in self.items.values() if i.state in OCCUPYING]


def apply(snap: Snapshot, event: dict) -> None:
    """Fold one event into the snapshot in place."""
    ts = event["ts"]
    match event["kind"]:
        case "context_created":
            snap.config = {
                "slot_cap": event["slot_cap"],
                "stall_after_days": event["stall_after_days"],
            }
        case "config_changed":
            snap.config[event["key"]] = event["value"]
        case "mission_created":
            snap.missions[event["slug"]] = event["title"]
        case "item_created":
            snap.items[event["id"]] = Item(
                event["id"], event["title"], event["mission"], created=ts, last_ts=ts
            )
        case "item_mapped" | "item_transitioned":
            item = snap.items.get(event["id"])
            if item is None:
                raise LedgerError(event["seq"], f"unknown item {event['id']}")
            item.last_ts = ts
            if event["kind"] == "item_mapped":
                item.mission = event["mission"]
            else:
                item.state = event["to"]
                if event.get("until") is not None:
                    item.until = event["until"]
                if event["edge"] == "override":
                    item.overrides += 1


def fold(events: list[dict]) -> Snapshot:
    snap = Snapshot()
    for event in events:
        apply(snap, event)
    return snap


def check(
    snap: Snapshot, item_id: int, edge: str, actor: str, human_allowed: bool = False
) -> Refusal | None:
    """Return the first rule that refuses this edge, or None if it may proceed.

    Raises NotFound when the item does not exist.
    """
    item = snap.item(item_id)
    allowed_from, _ = EDGES[edge]
    if item.state in TERMINAL:
        return Refusal(f"item {item_id} is {item.state}; no edges remain")
    if item.state not in allowed_from:
        return Refusal(f"{edge} is not permitted from {item.state}")
    if item.overrides > MAX_OVERRIDES and edge not in LOCK_ESCAPES:
        return Refusal(
            f"item {item_id} has been overridden {item.overrides} times; "
            "only delegate or drop remain"
        )
    if edge in {"pull", "override"} and item.mission is None:
        return Refusal(f"item {item_id} is not mapped to a mission; run `fw map {item_id} <slug>`")
    if edge == "pull" or (edge == "resume" and item.state == "waiting"):
        used, cap = len(snap.occupied()), snap.config["slot_cap"]
        if used >= cap:
            return Refusal(f"active column is full ({used}/{cap} slots)")
    if edge in HUMAN_ONLY and actor.startswith("agent:") and not human_allowed:
        return Refusal(f"{edge} requires a human; pass --human-allowed to record their permission")
    return None


def stall_pass(snap: Snapshot, now: datetime, stall_after_days: int) -> list[dict]:
    """Stall events (without `seq`) for active items idle longer than the threshold."""
    limit = timedelta(days=stall_after_days)
    return [
        {
            "ts": fmt_ts(now),
            "actor": "system",
            "kind": "item_transitioned",
            "id": item.id,
            "edge": "stall",
            "from": "active",
            "to": "stalled",
        }
        for item in snap.items.values()
        if item.state == "active" and now - parse_ts(item.last_ts) > limit
    ]


def status(snap: Snapshot, now: datetime) -> dict:
    items = list(snap.items.values())
    occupied = snap.occupied()
    cap = snap.config["slot_cap"]
    used = len(occupied)
    free = max(0, cap - used)
    dates = sorted(i.until for i in occupied if i.until)
    return {
        "active": [i.row() for i in occupied],
        "holding": [i.row() for i in items if i.state == "holding"],
        "waiting": sum(i.state == "waiting" for i in items),
        "delegated": sum(i.state == "delegated" for i in items),
        "slots_used": used,
        "slot_cap": cap,
        "slots_free": free,
        "next_open": now.date().isoformat() if free else (dates[0] if dates else None),
    }
