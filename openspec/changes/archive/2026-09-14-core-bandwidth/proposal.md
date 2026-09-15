## Why

`fw` prints its version and nothing else. Every product idea in AGENTS.md exists only as prose. This change builds the deterministic core that later changes plug into. It needs no language model, so a person at a shell or a coding agent (Claude Code, pi, opencode) can drive it today.

## What Changes

- `fw init` creates a local context: a directory with an append-only JSONL event log and a config (slot cap, default 3). No GitHub needed. A repo mirror is a later change.
- Missions: a small named list per context. Every item traces back to exactly one mission (Newport's "limit the big").
- Items are Newport's projects. Flat, one `mission` field. `fw add` creates an item in `holding`, mission optional at that point.
- Seven states: `holding`, `active`, `stalled`, `waiting`, `delegated`, `dropped`, `done`. Every transition is a recorded edge. Commands: `pull`, `done`, `drop`, `delegate`, `wait`, `resume`, `override`.
- `pull` fails when the active column is full or the item has no mission.
- Time is an input. Each command steps active items forward with `now` and records `stalled` by timestamp arithmetic. No daemon.
- After more than two overrides on one item, only `delegate` and `drop` remain.
- Actor on every event: `human` or `agent:<name>`. Pull is human-only. An agent records that it acted on its own with the human's permission.
- Every command accepts `--json`, never prompts, and uses stable exit codes.
- `fw status` prints both columns, slots used and free, and the earliest projected open date.
- `fw export` writes JSONL and CSV readable without `fw`.

## Capabilities

### New Capabilities

- `event-ledger`: contexts, `init`, the append-only JSONL log, event schema including actor, `export`.
- `bandwidth-graph`: missions, items, the seven states and edges, slot cap, stall arithmetic, override limit, human-only pull.
- `cli-interface`: command surface, `--json`, exit codes, non-interactive behavior, agent identification.

### Modified Capabilities

None. No specs exist yet.

## Non-goals

- GitHub Issues mirror.
- Natural-language intake, Apache Burr, the provider adapter, any model call.
- Capsules, context sync, protected time, daily goals, calendar shape.
- A TUI.

## Security and privacy

This change does not touch the capsule schema or protected time. It creates context isolation in its simplest form: one ledger directory per context, and no code path reads outside it or crosses between contexts.

Human-only pull is an honesty record, not a security boundary. An agent runs in the user's shell and could claim the human actor. The value is an auditable log of who acted, not a control that stops a misbehaving agent.

Ledger content is untrusted input. Every line is parsed against the event schema and a malformed line fails the command closed.

## Pull-based bandwidth

This change is the pull model. Items enter holding, a slot must be free to pull, and only a human may pull because it is their time. Nothing is pushed into the active column.

## Dependencies

No new runtime dependencies. The CLI uses stdlib `argparse` with subparsers, and tests call `main(argv)` directly. Click was considered for its decorators and `CliRunner`; rejected because argparse already ships and the tooling should stay boring. The idea is the interesting part.

## Impact

- New modules under `src/attention_firewall/`: ledger, graph, missions, and argparse subparsers extending the stub in `cli.py`. `--version` is preserved.
- New tests under `tests/` mirroring each module, plus end-to-end tests through `main(argv)`.
- README gains a quick start and a short section on calling `fw` from an agent.
