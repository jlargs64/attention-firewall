---
name: fw
description: Drive the attention-firewall CLI (fw) to read or change one person's bandwidth ledger. Use when the human asks about their active slots, holding column, when they can take new work, or asks you to add, map, or move an item.
---

# fw: the attention firewall

`fw` keeps a hard-capped Active column of slots and a Holding column for
everything else. Work is pulled into a slot by the human, never pushed.
Every change is an event appended to a local `events.jsonl` ledger.

## Rules

1. Pass `--json` on every call. Success is one JSON object on stdout with
   `ok: true`. Failure is an empty stdout and
   `{"ok": false, "code": N, "message": "..."}` on stderr.
2. Pass `--actor agent:<name>` naming yourself (`agent:pi`, `agent:opencode`,
   `agent:codex`, `agent:claude-code`) so the ledger records who acted.
3. Run `pull`, `override`, or `resume` only when the human asked for that
   specific action in the current conversation. Then add `--human-allowed`.
   Never run them on your own initiative; suggest them instead.
4. Exit codes 3 (refused) and 4 (not found) are answers. Report them to the
   human. Do not retry or work around them.
5. Run `fw --help` or `fw <command> --help` before guessing an invocation.
   The help text is generated from the parser and is always current.
6. Never edit `events.jsonl` directly. Only `fw` writes it.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Unexpected internal error |
| 2 | Usage error: bad option, argument, actor, or timestamp |
| 3 | Refused by a rule: invalid edge, column full, unmapped item, override lock, human-only edge, duplicate mission, already initialized |
| 4 | Not found: context not initialized, unknown item or mission |
| 5 | Malformed ledger line |

## Typical calls

```sh
fw status --json --actor agent:<name>
fw add "Review the Q4 deck" --mission ship-fw --json --actor agent:<name>
fw pull 3 --until 2026-10-01 --json --actor agent:<name> --human-allowed
```

`fw status` answers "when can you take this?": `next_open` is today if a slot
is free, otherwise the earliest `until` date among active items.
