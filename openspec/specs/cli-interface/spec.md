# cli-interface Specification

## Purpose

The command surface that humans and external agents share: one set of commands, machine-readable output on request, stable exit codes, and no interactive prompts.

## Requirements

### Requirement: Command surface
`fw` SHALL expose exactly these commands in this change: `init`, `mission add`, `mission list`, `add`, `map`, `pull`, `override`, `done`, `drop`, `delegate`, `wait`, `resume`, `status`, `log`, `config set`, `export`, and the `--version` option. `fw --help` and `fw <command> --help` SHALL describe every option well enough that an agent reading the text alone can form a valid invocation.

#### Scenario: Help lists commands
- **WHEN** `fw --help` runs
- **THEN** every command above appears in the output and the exit code is 0

#### Scenario: Version preserved
- **WHEN** `fw --version` runs
- **THEN** the package version is printed and the exit code is 0

### Requirement: Global options
Every command SHALL accept `--context PATH`, `--actor VALUE`, `--now TIMESTAMP`, and `--json`. `FW_CONTEXT` and `FW_ACTOR` environment variables SHALL supply defaults for the first two. A command-line option SHALL win over its environment variable.

#### Scenario: Option beats environment
- **WHEN** `FW_ACTOR=agent:pi fw add "x" --actor human` runs
- **THEN** the event records `actor: human`

#### Scenario: Invalid now
- **WHEN** `fw status --now yesterday` runs
- **THEN** the command exits with code 2 as a usage error

### Requirement: JSON output
With `--json`, a successful command SHALL write exactly one JSON object to stdout and nothing else. The object SHALL include `ok: true` and the command's result. `status --json` SHALL include `active`, `holding`, `waiting`, `delegated`, `slots_used`, `slot_cap`, `slots_free`, and `next_open`. Transition commands SHALL return the appended event. A refused or failed command with `--json` SHALL write one JSON object to stderr with `ok: false`, `code` (the exit code), and `message`. Without `--json`, output SHALL be human-readable text.

#### Scenario: Status as JSON
- **WHEN** `fw status --json` runs
- **THEN** stdout parses as one JSON object with the listed keys and exit code is 0

#### Scenario: Refusal as JSON
- **WHEN** `fw pull 9 --until 2026-10-01 --json` runs and item 9 does not exist
- **THEN** stdout is empty, stderr parses as `{"ok": false, "code": 4, "message": ...}`, and the exit code is 4

### Requirement: Exit codes
Exit codes SHALL be: 0 success; 1 unexpected internal error; 2 usage error (bad option, bad argument format, invalid actor or timestamp); 3 refused by a graph or ledger rule (invalid edge, column full, unmapped item, override lock, human-only edge, duplicate mission, already initialized); 4 not found (context not initialized, unknown item, unknown mission); 5 malformed ledger. The same condition SHALL produce the same code with and without `--json`.

#### Scenario: Codes are stable
- **WHEN** `fw done 1` is refused as an invalid edge, once with `--json` and once without
- **THEN** both invocations exit with code 3

### Requirement: Non-interactive
No command SHALL prompt for input, wait on stdin, or require a TTY. Every decision SHALL be expressible as an option or argument.

#### Scenario: Closed stdin
- **WHEN** `fw pull 1 --until 2026-10-01 < /dev/null` runs
- **THEN** it completes with the same result as with a terminal attached

### Requirement: Log inspection
`fw log [--item ID] [--limit N]` SHALL print events in `seq` order, newest last, optionally filtered to one item. With `--json` it SHALL return an array of event objects under `events`.

#### Scenario: Item history
- **WHEN** `fw log --item 1 --json` runs
- **THEN** `events` contains only events whose `id` is 1, in ascending `seq` order

### Requirement: Config changes are events
`fw config set slot-cap N` and `fw config set stall-days N` SHALL append a `config_changed` event with `key` and `value` (integer, at least 1). The effective value SHALL be the most recent `config_changed` for that key, else the value from `context_created`. Lowering `slot_cap` below the occupied count SHALL succeed and `status` SHALL show the excess.

#### Scenario: Raise the cap
- **WHEN** `fw config set slot-cap 4` runs
- **THEN** a `config_changed` event is appended and `status` reports `slot_cap: 4`

#### Scenario: Invalid value
- **WHEN** `fw config set slot-cap 0` runs
- **THEN** the command exits with code 2 and writes nothing
