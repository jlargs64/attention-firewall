"""One function per fw command: load, fold, stall pass, check, append one event, return a dict."""

import csv
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

from . import graph
from .ledger import LOG_NAME, NotFound, Refusal, append_event, fmt_ts, read_events

CONFIG_KEYS = {"slot-cap": "slot_cap", "stall-days": "stall_after_days"}
CSV_COLUMNS = ["id", "title", "mission", "state", "created", "last_event", "until", "overrides"]


def _event(actor: str, now: datetime, kind: str, **fields) -> dict:
    return {"ts": fmt_ts(now), "actor": actor, "kind": kind, **fields}


def _commit(ctx: Path, events: list[dict], event: dict) -> dict:
    """Assign the next seq, append to the log, and return the stored event."""
    event = {"seq": len(events) + 1, **event}
    append_event(ctx, event)
    events.append(event)
    return event


def _load(ctx: Path, now: datetime) -> tuple[graph.Snapshot, list[dict]]:
    """Read, fold, and run the stall pass, appending any stall events."""
    events = read_events(ctx)
    snap = graph.fold(events)
    for stall in graph.stall_pass(snap, now, snap.config["stall_after_days"]):
        graph.apply(snap, _commit(ctx, events, stall))
    return snap, events


def init(ctx: Path, actor: str, now: datetime, slots: int = 3, stall_days: int = 7) -> dict:
    if (ctx / LOG_NAME).exists():
        raise Refusal(f"context already initialized at {ctx / LOG_NAME}")
    ctx.mkdir(parents=True, exist_ok=True)
    created = _event(actor, now, "context_created", slot_cap=slots, stall_after_days=stall_days)
    return {"context": str(ctx), "event": _commit(ctx, [], created)}


def mission_add(ctx: Path, actor: str, now: datetime, slug: str, title: str | None = None) -> dict:
    snap, events = _load(ctx, now)
    if slug in snap.missions:
        raise Refusal(f"mission {slug} already exists")
    created = _event(actor, now, "mission_created", slug=slug, title=title or slug)
    return {"event": _commit(ctx, events, created)}


def mission_list(ctx: Path, now: datetime) -> dict:
    snap, _ = _load(ctx, now)
    return {
        "missions": [
            {
                "slug": slug,
                "title": title,
                "items": dict(Counter(i.state for i in snap.items.values() if i.mission == slug)),
            }
            for slug, title in snap.missions.items()
        ]
    }


def _need_mission(snap: graph.Snapshot, slug: str) -> None:
    if slug not in snap.missions:
        raise NotFound(f"mission {slug} not found")


def add(ctx: Path, actor: str, now: datetime, title: str, mission: str | None = None) -> dict:
    snap, events = _load(ctx, now)
    if mission is not None:
        _need_mission(snap, mission)
    item_id = max(snap.items, default=0) + 1
    created = _event(actor, now, "item_created", id=item_id, title=title, mission=mission)
    return {"event": _commit(ctx, events, created)}


def map_item(ctx: Path, actor: str, now: datetime, item_id: int, slug: str) -> dict:
    snap, events = _load(ctx, now)
    item = snap.item(item_id)
    _need_mission(snap, slug)
    if item.state in graph.TERMINAL:
        raise Refusal(f"item {item_id} is {item.state}; it cannot be mapped")
    mapped = _event(actor, now, "item_mapped", id=item_id, mission=slug)
    return {"event": _commit(ctx, events, mapped)}


def transition(
    ctx: Path,
    actor: str,
    now: datetime,
    edge: str,
    item_id: int,
    until: str | None = None,
    human_allowed: bool = False,
) -> dict:
    snap, events = _load(ctx, now)
    if refusal := graph.check(snap, item_id, edge, actor, human_allowed):
        raise refusal
    item = snap.item(item_id)
    fields: dict = {"id": item_id, "edge": edge, "from": item.state, "to": graph.EDGES[edge][1]}
    if edge in graph.DATED:
        fields["until"] = until
    if actor.startswith("agent:") and human_allowed:
        fields["human_allowed"] = True
    return {"event": _commit(ctx, events, _event(actor, now, "item_transitioned", **fields))}


def status(ctx: Path, now: datetime) -> dict:
    snap, _ = _load(ctx, now)
    return graph.status(snap, now)


def log(ctx: Path, now: datetime, item: int | None = None, limit: int | None = None) -> dict:
    _, events = _load(ctx, now)
    if item is not None:
        events = [e for e in events if e.get("id") == item]
    if limit:
        events = events[-limit:]
    return {"events": events}


def config_set(ctx: Path, actor: str, now: datetime, key: str, value: int) -> dict:
    _, events = _load(ctx, now)
    changed = _event(actor, now, "config_changed", key=CONFIG_KEYS[key], value=value)
    return {"event": _commit(ctx, events, changed)}


def export(ctx: Path, fmt: str, out: Path) -> dict:
    """Write the ledger as plain jsonl or csv to `out`. Appends nothing, so no stall pass."""
    events = read_events(ctx)
    if fmt == "jsonl":
        shutil.copyfile(ctx / LOG_NAME, out)
    else:
        snap = graph.fold(events)
        with out.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            for i in snap.items.values():
                writer.writerow(
                    {
                        "id": i.id,
                        "title": i.title,
                        "mission": i.mission or "",
                        "state": i.state,
                        "created": i.created,
                        "last_event": i.last_ts,
                        "until": i.until or "",
                        "overrides": i.overrides,
                    }
                )
    return {"out": str(out), "format": fmt, "events": len(events)}
