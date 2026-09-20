## Context

See proposal.md for motivation and the three specs under `specs/` for behavior. Current code is a version-only `argparse` stub with no runtime dependencies. Constraints that shape this design: stdlib only, no daemon, JSONL as the single source of truth, provider-agnostic with no model call in this change, and a CLI that external agents drive through `--json` and exit codes.

## Goals / Non-Goals

**Goals:**
- One module decides state. Everything else is parsing, printing, and file I/O.
- Derived state (current item states, occupied slots, override counts) is always recomputed from the log. There is no second store to drift.
- A refused command never writes. Validation happens fully before the append.
- A test can run any scenario in the specs without a network, a clock, or a TTY.

**Non-Goals:**
- Performance beyond a few thousand events. Replaying the whole log on every command is the intended design at this scale.
- Concurrency across processes. One human, one shell, one context.
- Any Burr code. See "Where Burr fits" below for how this design leaves room for it.

## Decisions

**Four modules: `ledger.py`, `graph.py`, `commands.py`, `cli.py`.**
`ledger` reads and appends JSONL and validates each line against the event schema. `graph` is pure functions: fold events into item state, decide whether an edge is permitted, compute slots, stall, and `next_open`. `commands` glues them: load, fold, decide, append, return a result dict. `cli` is argparse subparsers that build argv into a call and format the result as text or JSON. Alternative: one file. Rejected because the state rules must be testable without touching the filesystem.

**State is a fold over events, recomputed every run.**
`graph.fold(events) -> Snapshot` where the snapshot holds items by id, missions, and effective config. Every command loads the log, folds, applies the stall pass at `now`, appends any stall events, then evaluates the requested edge against the new snapshot. Alternative: a materialized `state.json` cache. Rejected: a second copy of the truth that can disagree with the log, for no measurable gain under a few thousand lines. `# ponytail: full replay per command, add a snapshot cache if a log passes ~50k lines`.

**Edges are a static table, checked before any write.**
A dict of `edge -> (allowed_from, to)` mirrors the spec table exactly. `graph.check(snapshot, item_id, edge, actor, human_allowed) -> None | Refusal`. The check runs cap, mission, override-lock, and human-only rules in a fixed order and returns the first refusal. Only after `None` does `commands` append. This is the invariant "every transition is an edge" in code form.

**Time enters through `now` only.**
The stall pass and every `ts` use one `now` value resolved once per invocation: `--now` if given, else `datetime.now(UTC)`. No module calls the clock itself. This makes the "two-week absence replayed" scenario a plain unit test.

**Actors are validated by regex at the CLI boundary.**
`human`, `system`, or `agent:[a-z0-9._-]+`. `system` is refused as a command-line actor; only the stall pass emits it. `--human-allowed` is a flag on `pull`, `override`, and `resume` and is written to the event only when the actor is an agent.

**Context path resolution: `--context`, then `FW_CONTEXT`, then `$XDG_DATA_HOME/fw`, then `~/.local/share/fw`.**
Bandwidth belongs to a person on a machine, not to a working directory, so the default is a user data path rather than a git-style `.fw/` walk-up. Alternative: cwd walk-up. Rejected because it invites one context per project folder, which is the opposite of the two-column idea.

**Event schema validation is a hand-written check per kind.**
A `REQUIRED: dict[kind, dict[field, type]]` table and one function. Alternative: `jsonschema` or `pydantic`. Rejected: a dependency for six event kinds. Malformed lines raise `LedgerError(line_no)` which `cli` maps to exit 5.

**Ids are sequential integers derived from the fold.**
Next item id is `max(ids) + 1`. Mission ids are their slugs. Alternative: ULIDs. Rejected: a human types these at a shell several times a day.

**Config lives in the log.**
`context_created` carries the initial values and `config_changed` overrides them. Effective config is part of the fold. No `config.json`.

**Output formatting is one function per command result.**
`--json` dumps the result dict with `ok: true`. Text mode formats the same dict. Errors are a `Refusal` or `LedgerError` caught in `cli.main`, printed to stderr as text or JSON, and mapped to the exit code table in the `cli-interface` spec.

**Where Burr fits later.**
The intake change will add a Burr application whose actions call `commands.*` with `actor="agent:fw-intake"` and never touch `ledger` or `graph` directly. Stall detection stays in `graph` and is not moved into Burr; Burr will drive per-item follow-up flows, not the state rules. Provider access will go through one adapter module that Burr actions import. Nothing in this change references any of that; the seam is the `commands` module's function signatures.

**Provider adapter, offline, and capsule failure modes.**
There is no provider adapter, no network, and no capsule in this change. Offline is the only mode. A stale or malformed capsule cannot occur because no capsule is read. Noted so the absence is not mistaken for an omission.

## Risks / Trade-offs

- [Full replay grows slow] → Measured, not guessed. Add a snapshot cache behind the same `fold` signature if a real log crosses tens of thousands of events.
- [Two processes append at once and interleave lines] → Out of scope for one human at one shell. If it appears, `fcntl.flock` on the log file is a five-line fix.
- [Sequential `seq` breaks after a manual edit to the log] → That is the point. Exit 5 and name the line; the user owns the file and fixes it by hand.
- [Agent claims `--actor human`] → Documented as an honesty record. No mitigation by design.
- [`--until` required on pull annoys users] → It is the only way `next_open` can ever be a date instead of null. Kept.
- [Stall events accumulate on every command during a long absence] → Each active item stalls once; a stalled item does not re-stall. Bounded by slot count.

## Migration Plan

Greenfield. `fw init` on an existing machine creates a new context. Rollback is deleting the context directory. The event schema carries no version field yet; if a later change needs one, `context_created` gains `schema: 1` and the fold treats its absence as 1.

## Open Questions

- Whether `delegate` should record who received the work. Left out; a later change can add an optional field to the event without a log migration.
- Default `stall_after_days` of 7 is a guess. It is a config value and can change without touching specs.
