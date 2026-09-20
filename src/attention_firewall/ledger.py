"""Append-only JSONL event log: context paths, schema validation, read, append."""

import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path


class FwError(Exception):
    """Base for errors that map to an exit code."""

    code = 1


class UsageError(FwError):
    code = 2


class Refusal(FwError):
    code = 3


class NotFound(FwError):
    code = 4


class LedgerError(FwError):
    code = 5

    def __init__(self, line_no: int, message: str) -> None:
        super().__init__(f"{LOG_NAME} line {line_no}: {message}")
        self.line_no = line_no


LOG_NAME = "events.jsonl"
ACTOR_RE = re.compile(r"^(human|system|agent:[a-z0-9._-]+)$")
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
STATES = frozenset({"holding", "active", "stalled", "waiting", "delegated", "dropped", "done"})

_STR_OR_NONE = (str, type(None))
BASE = {"seq": int, "ts": str, "actor": str, "kind": str}
REQUIRED: dict[str, dict[str, object]] = {
    "context_created": {"slot_cap": int, "stall_after_days": int},
    "config_changed": {"key": str, "value": int},
    "mission_created": {"slug": str, "title": str},
    "item_created": {"id": int, "title": str, "mission": _STR_OR_NONE},
    "item_mapped": {"id": int, "mission": str},
    "item_transitioned": {"id": int, "edge": str, "from": str, "to": str},
}
OPTIONAL: dict[str, dict[str, object]] = {
    "item_transitioned": {"until": _STR_OR_NONE, "human_allowed": bool},
}


def fmt_ts(when: datetime) -> str:
    return when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(text: str) -> datetime:
    """Parse ISO 8601; naive values are taken as UTC. Raises ValueError."""
    when = datetime.fromisoformat(text)
    return when.replace(tzinfo=UTC) if when.tzinfo is None else when.astimezone(UTC)


def _typed(value: object, typ: object) -> bool:
    if typ is int:
        return type(value) is int  # bool is an int subclass; reject it
    return isinstance(value, typ)  # type: ignore[arg-type]


def validate(event: object, line_no: int) -> None:
    """Check one event against the schema for its kind. Raises LedgerError."""
    if not isinstance(event, dict):
        raise LedgerError(line_no, "not a JSON object")
    kind = event.get("kind")
    if kind not in REQUIRED:
        raise LedgerError(line_no, f"unknown kind {kind!r}")
    for field, typ in (BASE | REQUIRED[kind]).items():
        if field not in event:
            raise LedgerError(line_no, f"missing field {field!r}")
        if not _typed(event[field], typ):
            raise LedgerError(line_no, f"field {field!r} has the wrong type")
    for field, typ in OPTIONAL.get(kind, {}).items():
        if field in event and not _typed(event[field], typ):
            raise LedgerError(line_no, f"field {field!r} has the wrong type")
    if not ACTOR_RE.match(event["actor"]):
        raise LedgerError(line_no, f"invalid actor {event['actor']!r}")
    try:
        parse_ts(event["ts"])
    except ValueError:
        raise LedgerError(line_no, f"invalid timestamp {event['ts']!r}") from None
    if kind == "item_transitioned" and not {event["from"], event["to"]} <= STATES:
        raise LedgerError(line_no, "unknown state")


def resolve_context(path_opt: str | None, env: Mapping[str, str]) -> Path:
    """`--context`, then FW_CONTEXT, then $XDG_DATA_HOME/fw, then ~/.local/share/fw."""
    if path_opt:
        return Path(path_opt)
    if env.get("FW_CONTEXT"):
        return Path(env["FW_CONTEXT"])
    base = env.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "fw"


def read_events(ctx: Path) -> list[dict]:
    """Read and validate every line. Never repairs or skips."""
    log = ctx / LOG_NAME
    if not log.is_file():
        raise NotFound(f"context not initialized at {ctx}; run `fw init`")
    events: list[dict] = []
    with log.open("rb") as fh:
        for line_no, raw in enumerate(fh, 1):
            try:
                event = json.loads(raw)
            except ValueError:
                raise LedgerError(line_no, "not valid JSON") from None
            validate(event, line_no)
            if event["seq"] != line_no:
                raise LedgerError(line_no, f"seq {event['seq']} breaks the sequence")
            events.append(event)
    return events


def append_event(ctx: Path, event: dict) -> None:
    validate(event, event.get("seq", 0))
    with (ctx / LOG_NAME).open("ab") as fh:
        fh.write(json.dumps(event).encode() + b"\n")
