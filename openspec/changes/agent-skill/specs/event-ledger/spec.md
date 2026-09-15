## MODIFIED Requirements

### Requirement: Context initialization
`fw init` SHALL create a context directory containing an empty event log and SHALL append a `context_created` event carrying `slot_cap` (integer, default 3) and `stall_after_days` (integer, default 7). The context path SHALL default to `$XDG_DATA_HOME/fw` (falling back to `~/.local/share/fw`) and SHALL be overridable by `--context PATH` or the `FW_CONTEXT` environment variable. `fw init` SHALL require no network access and no credentials.

#### Scenario: First init
- **WHEN** `fw init` runs and no context exists at the resolved path
- **THEN** the directory and `events.jsonl` are created, the first line is a `context_created` event with `slot_cap: 3` and `stall_after_days: 7`, and the exit code is 0

#### Scenario: Init with custom cap
- **WHEN** `fw init --slots 2 --stall-days 10` runs
- **THEN** the `context_created` event records `slot_cap: 2` and `stall_after_days: 10`

#### Scenario: Init on existing context
- **WHEN** `fw init` runs and `events.jsonl` already exists at the resolved path
- **THEN** nothing is written, an error names the existing path, and the exit code is 3

#### Scenario: Command before init
- **WHEN** any command other than `init`, `skill show`, `skill install`, `--version`, or `--help` runs and no context exists at the resolved path
- **THEN** the command writes nothing, reports that the context is not initialized, and exits with code 4
