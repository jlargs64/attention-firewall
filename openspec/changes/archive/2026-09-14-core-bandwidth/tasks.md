## 1. Branch and ledger

- [x] 1.1 Create branch `core-bandwidth` from `main` and verify `git branch --show-current` prints it. No new dependencies; confirm `pyproject.toml` `dependencies` stays `[]`.
- [x] 1.2 Add `src/attention_firewall/ledger.py` with `resolve_context(path_opt, env)`, `read_events(path) -> list[dict]`, `append_event(path, event)`, and per-kind schema validation raising `LedgerError(line_no)`. Verify with `tests/test_ledger.py` covering: init creates the directory and first line, append preserves prior bytes, contiguous `seq`, truncated line and unknown kind both raise with the right line number, and `--context` beats `FW_CONTEXT` beats the XDG default.
- [x] 1.3 Add actor validation (`human`, `agent:[a-z0-9._-]+`, `system` only from the stall pass) and verify `tests/test_ledger.py` rejects `robot` and accepts `agent:claude`.
- [x] 1.4 Quality gate: `uv run ruff check . && uv run ruff format --check .`, `uv run pytest --cov --cov-fail-under=70`, and `uv run pre-commit run --all-files` all pass.

## 2. Graph

- [x] 2.1 Add `src/attention_firewall/graph.py` with `Snapshot` (items, missions, effective config) and `fold(events) -> Snapshot`. Verify `tests/test_graph.py` folds a fixture log into expected item states, mission list, and config with `config_changed` overriding `context_created`.
- [x] 2.2 Add the static edge table matching the spec exactly and `check(snapshot, item_id, edge, actor, human_allowed) -> Refusal | None` applying, in order: item exists, not terminal, edge permitted from current state, override lock, mission present for pull/override, slot cap for pull and resume-from-waiting, human-only for pull/override/resume. Verify `tests/test_graph.py` has one test per scenario under "Item states and edges", "Slot cap on pull", "Pull is a human decision", and "Override bypasses the cap and is limited".
- [x] 2.3 Add `stall_pass(snapshot, now, stall_after_days) -> list[event]` using timestamp arithmetic only. Verify tests for: stall after threshold, not yet stalled, two items stalled in one call after a long absence, activity resets the clock, and a stalled item is not stalled twice.
- [x] 2.4 Add `status(snapshot, now)` returning `active`, `holding`, `waiting`, `delegated`, `slots_used`, `slot_cap`, `slots_free` (floored at 0), and `next_open`. Verify tests for free slot, full column with dates, and overridden column.
- [x] 2.5 Quality gate: `uv run ruff check . && uv run ruff format --check .`, `uv run pytest --cov --cov-fail-under=70`, and `uv run pre-commit run --all-files` all pass.

## 3. Commands

- [x] 3.1 Add `src/attention_firewall/commands.py` with one function per command (`init`, `mission_add`, `mission_list`, `add`, `map_item`, `transition` for pull/override/done/drop/delegate/wait/resume, `status`, `log`, `config_set`, `export`). Each loads, folds, runs the stall pass and appends its events, checks, appends exactly one event on success, and returns a result dict. Verify `tests/test_commands.py` shows a refused transition leaves the log byte-identical and a success appends one line.
- [x] 3.2 Implement `export` for `jsonl` (byte-identical copy) and `csv` (header plus one row per item with the spec's columns), writing only to `--out`. Verify tests compare bytes for jsonl and row count and header for csv, and that the log is unchanged.
- [x] 3.3 Implement `config_set` with keys `slot-cap` and `stall-days`, integers at least 1. Verify tests for raising the cap, lowering it below the occupied count, and rejecting 0.
- [x] 3.4 Quality gate: `uv run ruff check . && uv run ruff format --check .`, `uv run pytest --cov --cov-fail-under=70`, and `uv run pre-commit run --all-files` all pass.

## 4. CLI

- [x] 4.1 Extend `src/attention_firewall/cli.py` with argparse subparsers for every command in the `cli-interface` spec, global options `--context`, `--actor`, `--now`, `--json` with `FW_CONTEXT` and `FW_ACTOR` defaults, and `--human-allowed` on pull, override, resume. Keep `--version`. Verify `tests/test_cli.py` checks `fw --help` names every command and `--version` still passes.
- [x] 4.2 Map exceptions to exit codes in `main`: usage 2, `Refusal` 3, not found 4, `LedgerError` 5, anything else 1. Text errors to stderr; with `--json`, one object `{"ok": false, "code", "message"}` on stderr and nothing on stdout. Verify tests for each code with and without `--json` producing the same code.
- [x] 4.3 Implement text and JSON formatting for every result, with `--json` writing exactly one object containing `ok: true`. Verify tests parse `status --json` and `log --item 1 --json` and check the listed keys.
- [x] 4.4 Verify non-interactive behavior: a test runs `fw pull` through `subprocess` with `stdin=subprocess.DEVNULL` and gets the same result as a direct `main(argv)` call.
- [x] 4.5 Write `tests/test_end_to_end.py` walking the spec's story through `main(argv)` against a temp context: init, two missions, four items, pull three, refused fourth pull, agent pull refused then allowed with `--human-allowed`, wait frees a slot, override past the cap, third override locks the item, stall after `--now` jump, status `next_open` is the earliest `until`, export both formats, two contexts stay isolated.
- [x] 4.6 Quality gate: `uv run ruff check . && uv run ruff format --check .`, `uv run pytest --cov --cov-fail-under=70`, and `uv run pre-commit run --all-files` all pass.

## 5. Docs and PR

- [x] 5.1 Update `README.md` with a quick start (init, mission add, add, pull, status) and a short "Calling fw from an agent" section covering `--json`, `--actor agent:<name>`, `--human-allowed`, and the exit code table. Verify by reading it against the `cli-interface` spec.
- [ ] 5.2 Open a pull request from `core-bandwidth` to `main` with the proposal's "Security and privacy" section in the description and verify the `gate` check is green. Do not merge; the maintainer reviews.
- [x] 5.3 Quality gate: `uv run ruff check . && uv run ruff format --check .`, `uv run pytest --cov --cov-fail-under=70`, and `uv run pre-commit run --all-files` all pass.
