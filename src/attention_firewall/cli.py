"""Command-line entry point for `fw`: argparse subparsers, output formatting, exit codes."""

import argparse
import json
import os
import sys
from collections.abc import Mapping
from datetime import UTC, date, datetime
from importlib.metadata import version
from pathlib import Path

from . import commands, skill
from .ledger import ACTOR_RE, SLUG_RE, FwError, UsageError, parse_ts, resolve_context

# --- argument types (each raises ArgumentTypeError -> exit 2) ----------------


def actor_type(value: str) -> str:
    if value == "system" or not ACTOR_RE.match(value):
        raise argparse.ArgumentTypeError(f"actor must be 'human' or 'agent:<name>', got {value!r}")
    return value


def slug_type(value: str) -> str:
    if not SLUG_RE.match(value):
        raise argparse.ArgumentTypeError(f"slug must be kebab-case (a-z, 0-9, -), got {value!r}")
    return value


def now_type(value: str) -> datetime:
    try:
        return parse_ts(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an ISO 8601 timestamp: {value!r}") from None


def date_type(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an ISO 8601 date: {value!r}") from None


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an integer: {value!r}") from None
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


# --- parser -----------------------------------------------------------------


class Parser(argparse.ArgumentParser):
    """argparse that raises instead of exiting so `main` owns the exit code and format."""

    def error(self, message: str) -> None:  # type: ignore[override]
        raise UsageError(message)


def _globals(parser: argparse.ArgumentParser, env: Mapping[str, str] | None) -> None:
    """Global options. With `env`, defaults come from it; without, they are suppressed so
    a subcommand's copy never overwrites a value given before the command name."""
    suppress = env is None
    env = env or {}
    parser.add_argument(
        "--context",
        metavar="PATH",
        default=argparse.SUPPRESS if suppress else env.get("FW_CONTEXT"),
        help="context directory (default: $FW_CONTEXT, then $XDG_DATA_HOME/fw)",
    )
    parser.add_argument(
        "--actor",
        type=actor_type,
        default=argparse.SUPPRESS if suppress else env.get("FW_ACTOR") or "human",
        help="who is acting: 'human' or 'agent:<name>' (default: $FW_ACTOR, then human)",
    )
    parser.add_argument(
        "--now",
        type=now_type,
        metavar="TIMESTAMP",
        default=argparse.SUPPRESS if suppress else None,
        help="treat this ISO 8601 timestamp as the current time (default: UTC now)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS if suppress else False,
        help="write one JSON object to stdout instead of text",
    )


def _item_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("id", type=int, help="item id, as shown by `fw status`")


def build_parser(env: Mapping[str, str]) -> Parser:
    parser = Parser(
        prog="fw",
        description="Attention firewall: a hard-capped Active column and a Holding column. "
        "Work is pulled into a free slot, never pushed.",
    )
    parser.add_argument("--version", action="version", version=version("attention-firewall"))
    _globals(parser, env)
    common = argparse.ArgumentParser(add_help=False)
    _globals(common, None)
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    def cmd(parent, name: str, help_text: str, run, fmt) -> argparse.ArgumentParser:
        p = parent.add_parser(name, help=help_text, description=help_text, parents=[common])
        p.set_defaults(run=run, fmt=fmt)
        return p

    p = cmd(sub, "init", "Create a context with an empty event log.", run_init, fmt_init)
    p.add_argument("--slots", type=positive_int, default=3, help="slot cap (default 3)")
    p.add_argument(
        "--stall-days", type=positive_int, default=7, help="days idle before stall (default 7)"
    )

    mission = sub.add_parser("mission", help="Manage missions.", parents=[common])
    mission_sub = mission.add_subparsers(dest="subcommand", required=True, metavar="<subcommand>")
    p = cmd(mission_sub, "add", "Add a mission.", run_mission_add, fmt_event)
    p.add_argument("slug", type=slug_type, help="kebab-case id, unique in the context")
    p.add_argument("--title", help="human title (default: the slug)")
    cmd(
        mission_sub,
        "list",
        "List missions with item counts per state.",
        run_mission_list,
        fmt_missions,
    )

    p = cmd(sub, "add", "Add an item to the Holding column.", run_add, fmt_event)
    p.add_argument("title")
    p.add_argument("--mission", type=slug_type, help="mission slug (must exist)")

    p = cmd(sub, "map", "Map an item to a mission.", run_map, fmt_event)
    _item_arg(p)
    p.add_argument("slug", type=slug_type)

    for edge, help_text in EDGE_HELP.items():
        p = cmd(sub, edge, help_text, run_transition, fmt_event)
        _item_arg(p)
        if edge in ("pull", "override", "resume"):
            p.add_argument(
                "--until",
                type=date_type,
                metavar="DATE",
                required=edge != "resume",
                help="projected date the slot frees up (ISO 8601)",
            )
            p.add_argument(
                "--human-allowed",
                action="store_true",
                help="record that an agent acted with the human's permission",
            )

    cmd(
        sub,
        "status",
        "Show both columns, slot use, and the next open date.",
        run_status,
        fmt_status,
    )

    p = cmd(sub, "log", "Print events in seq order.", run_log, fmt_log)
    p.add_argument("--item", type=int, metavar="ID", help="only events for this item")
    p.add_argument("--limit", type=positive_int, metavar="N", help="only the last N events")

    config = sub.add_parser("config", help="Change context settings.", parents=[common])
    config_sub = config.add_subparsers(dest="subcommand", required=True, metavar="<subcommand>")
    p = cmd(config_sub, "set", "Set a config value (recorded as an event).", run_config, fmt_event)
    p.add_argument("key", choices=sorted(commands.CONFIG_KEYS))
    p.add_argument("value", type=positive_int)

    p = cmd(sub, "export", "Write the ledger to a plain file.", run_export, fmt_export)
    p.add_argument("--format", choices=["jsonl", "csv"], required=True)
    p.add_argument("--out", type=Path, required=True, metavar="PATH")

    skills = sub.add_parser(
        "skill",
        help="Show or install the agent skill that teaches agents to call fw.",
        parents=[common],
    )
    skills_sub = skills.add_subparsers(dest="subcommand", required=True, metavar="<subcommand>")
    cmd(skills_sub, "show", "Print SKILL.md to stdout.", run_skill_show, fmt_skill_show)
    p = cmd(
        skills_sub,
        "install",
        "Write SKILL.md to <dir>/fw/SKILL.md for each detected or named agent. "
        "Needs no context. Re-run after upgrading fw to refresh the skill.",
        run_skill_install,
        fmt_skill_install,
    )
    p.add_argument(
        "--agent",
        action="append",
        default=[],
        choices=sorted(skill.AGENTS),
        metavar="NAME",
        help=f"install for this agent only (repeatable): {', '.join(sorted(skill.AGENTS))}",
    )
    p.add_argument(
        "--project",
        action="store_true",
        help="use each agent's project-level path under the current directory",
    )
    p.add_argument(
        "--dir", type=Path, metavar="PATH", help="write to PATH/fw/SKILL.md and nowhere else"
    )
    return parser


EDGE_HELP = {
    "pull": "Pull a holding item into a free active slot (human only).",
    "override": "Force a holding item active past the slot cap (human only, limited).",
    "done": "Mark an active, stalled, or delegated item done.",
    "drop": "Drop an item. Terminal.",
    "delegate": "Hand an item to someone else; it frees its slot.",
    "wait": "Park an active or stalled item while waiting on a stakeholder; frees its slot.",
    "resume": "Bring a waiting or stalled item back to active (human only).",
}

# --- runners: argparse namespace -> commands.* --------------------------------


def run_init(ns, ctx, actor, now):
    return commands.init(ctx, actor, now, ns.slots, ns.stall_days)


def run_mission_add(ns, ctx, actor, now):
    return commands.mission_add(ctx, actor, now, ns.slug, ns.title)


def run_mission_list(ns, ctx, actor, now):
    return commands.mission_list(ctx, now)


def run_add(ns, ctx, actor, now):
    return commands.add(ctx, actor, now, ns.title, ns.mission)


def run_map(ns, ctx, actor, now):
    return commands.map_item(ctx, actor, now, ns.id, ns.slug)


def run_transition(ns, ctx, actor, now):
    until = getattr(ns, "until", None)
    human_allowed = getattr(ns, "human_allowed", False)
    return commands.transition(ctx, actor, now, ns.command, ns.id, until, human_allowed)


def run_status(ns, ctx, actor, now):
    return commands.status(ctx, now)


def run_log(ns, ctx, actor, now):
    return commands.log(ctx, now, ns.item, ns.limit)


def run_config(ns, ctx, actor, now):
    return commands.config_set(ctx, actor, now, ns.key, ns.value)


def run_export(ns, ctx, actor, now):
    return commands.export(ctx, ns.format, ns.out)


def run_skill_show(ns, ctx, actor, now):
    return {"skill": skill.text()}


def run_skill_install(ns, ctx, actor, now):
    written = skill.install(ns.agent, ns.project, ns.dir, Path.home(), Path.cwd())
    return {"installed": [str(path) for path in written]}


# --- text formatters ----------------------------------------------------------


def fmt_init(result: dict) -> str:
    event = result["event"]
    return (
        f"initialized {result['context']} "
        f"(slot cap {event['slot_cap']}, stall after {event['stall_after_days']} days)"
    )


def fmt_event(result: dict) -> str:
    e = result["event"]
    match e["kind"]:
        case "mission_created":
            return f"mission {e['slug']} added: {e['title']}"
        case "item_created":
            return f"item {e['id']} added to holding: {e['title']}"
        case "item_mapped":
            return f"item {e['id']} mapped to {e['mission']}"
        case "config_changed":
            return f"{e['key']} = {e['value']}"
        case _:
            until = f" until {e['until']}" if e.get("until") else ""
            return f"item {e['id']}: {e['from']} -> {e['to']}{until}"


def fmt_missions(result: dict) -> str:
    if not result["missions"]:
        return "no missions; add one with `fw mission add <slug> --title TEXT`"
    return "\n".join(
        f"{m['slug']}  {m['title']}  "
        + " ".join(f"{state}={n}" for state, n in sorted(m["items"].items()))
        for m in result["missions"]
    )


def _item_line(item: dict) -> str:
    mission = f" [{item['mission']}]" if item["mission"] else ""
    until = f"  until {item['until']}" if item["until"] else ""
    return f"  {item['id']:>3}  {item['state']:<8}{until:<18}  {item['title']}{mission}"


def fmt_status(result: dict) -> str:
    lines = [
        f"Active ({result['slots_used']}/{result['slot_cap']} slots, {result['slots_free']} free)",
        *(_item_line(i) for i in result["active"]),
        "Holding",
        *(_item_line(i) for i in result["holding"]),
        f"Waiting: {result['waiting']}  Delegated: {result['delegated']}",
        f"Next open: {result['next_open'] or 'unknown (no until dates on active items)'}",
    ]
    return "\n".join(lines)


def fmt_log(result: dict) -> str:
    skip = {"seq", "ts", "actor", "kind"}
    return "\n".join(
        f"{e['seq']:>4}  {e['ts']}  {e['actor']:<14}  {e['kind']:<17}  "
        + " ".join(f"{k}={v}" for k, v in e.items() if k not in skip)
        for e in result["events"]
    )


def fmt_export(result: dict) -> str:
    return f"wrote {result['format']} to {result['out']} ({result['events']} events)"


def fmt_skill_show(result: dict) -> str:
    return result["skill"].removesuffix("\n")  # print() adds the newline back


def fmt_skill_install(result: dict) -> str:
    return "\n".join(f"wrote {path}" for path in result["installed"])


# --- entry point ----------------------------------------------------------------


def _fail(code: int, message: str, as_json: bool) -> None:
    if as_json:
        print(json.dumps({"ok": False, "code": code, "message": message}), file=sys.stderr)
    else:
        print(f"fw: {message}", file=sys.stderr)
    sys.exit(code)


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv) or ["--help"]  # bare `fw` shows help
    as_json = "--json" in argv
    env = os.environ
    try:
        ns = build_parser(env).parse_args(argv)
        now = ns.now or datetime.now(UTC)
        ctx = resolve_context(ns.context, env)
        result = ns.run(ns, ctx, ns.actor, now)
    except FwError as exc:
        _fail(exc.code, str(exc), as_json)
    except Exception as exc:  # noqa: BLE001 - anything unexpected is exit 1, never a traceback
        _fail(1, f"{type(exc).__name__}: {exc}", as_json)
    if ns.json:
        print(json.dumps({"ok": True, **result}))
    else:
        print(ns.fmt(result))


if __name__ == "__main__":
    main()
