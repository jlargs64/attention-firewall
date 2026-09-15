## Purpose

Lets external coding agents discover `fw` and use it correctly: a packaged skill file in the open Agent Skills format, a command that prints it, and a command that installs it into the agent directories on the user's machine.

## ADDED Requirements

### Requirement: Skill file format
`fw` SHALL ship a skill file named `SKILL.md` in the Agent Skills format: YAML frontmatter with `name: fw` and a `description` of 1 to 1024 characters that says what `fw` does and when an agent should use it, followed by a markdown body. The body SHALL be under 100 lines and SHALL state each of these rules: pass `--json` on every call; pass `--actor agent:<name>` naming the agent; run `pull`, `override`, or `resume` only when the human asked for that specific action in the current conversation, and then add `--human-allowed`; treat exit codes 3 and 4 as answers to report, not errors to retry; run `fw --help` or `fw <command> --help` before guessing an invocation; never edit `events.jsonl` directly. The body SHALL list the meaning of exit codes 0 through 5.

#### Scenario: Frontmatter is valid
- **WHEN** the skill file is parsed
- **THEN** the frontmatter has `name` equal to `fw` and a non-empty `description` no longer than 1024 characters

#### Scenario: Rules are present
- **WHEN** the skill body is read
- **THEN** it mentions `--json`, `--actor agent:`, `--human-allowed`, `fw --help`, `events.jsonl`, and each exit code 0 through 5, and it is under 100 lines

### Requirement: Packaged copy matches repository copy
The skill SHALL be included in the installed package so `fw` can read it without network access, and an identical copy SHALL exist at `skills/fw/SKILL.md` in the repository for skill installers that scan repositories. The two copies SHALL be byte-identical.

#### Scenario: Copies agree
- **WHEN** the packaged skill and `skills/fw/SKILL.md` are compared
- **THEN** their bytes are identical

#### Scenario: Wheel carries the skill
- **WHEN** the package is built
- **THEN** the wheel contains the skill file and `fw skill show` works from a clean install with no repository checkout

### Requirement: Show the skill
`fw skill show` SHALL write the skill file to stdout unchanged and exit 0. With `--json` it SHALL write one object with `ok: true` and `skill` holding the file text. It SHALL require no initialized context and SHALL read no ledger.

#### Scenario: Show before init
- **WHEN** `fw skill show` runs on a machine with no context
- **THEN** stdout is the skill file text and the exit code is 0

#### Scenario: Show as JSON
- **WHEN** `fw skill show --json` runs
- **THEN** stdout parses as `{"ok": true, "skill": "..."}` where `skill` equals the file text

### Requirement: Install the skill into agent directories
`fw skill install` SHALL write the skill to `<dir>/fw/SKILL.md` for each target directory, creating directories as needed and overwriting an existing file, so a re-run after upgrading `fw` refreshes the skill. Target directories SHALL come from, in order of precedence: `--dir PATH` (that path, once); `--agent NAME` (repeatable, from the agent table); otherwise every agent whose user-level home directory exists. `--project` SHALL select each agent's project-level path relative to the current directory instead of its user-level path. The result SHALL list every path written; with `--json` under `installed`. Naming an unknown agent SHALL exit 2. Detecting no agent when neither `--agent` nor `--dir` is given SHALL exit 4 with a message naming the flags. The command SHALL require no initialized context and SHALL read no ledger.

The agent table SHALL be:

| agent | detected by | user-level path | project-level path |
|---|---|---|---|
| claude-code | `~/.claude` | `~/.claude/skills` | `.claude/skills` |
| pi | `~/.pi/agent` | `~/.pi/agent/skills` | `.pi/skills` |
| opencode | `~/.config/opencode` | `~/.config/opencode/skills` | `.agents/skills` |
| codex | `~/.codex` | `~/.codex/skills` | `.agents/skills` |

#### Scenario: Detected agents
- **WHEN** `fw skill install` runs and `~/.pi/agent` and `~/.claude` exist but `~/.codex` and `~/.config/opencode` do not
- **THEN** `~/.pi/agent/skills/fw/SKILL.md` and `~/.claude/skills/fw/SKILL.md` are written and nothing else is

#### Scenario: Named agent, project scope
- **WHEN** `fw skill install --agent opencode --project` runs in a project directory
- **THEN** `.agents/skills/fw/SKILL.md` is written under the current directory

#### Scenario: Explicit directory
- **WHEN** `fw skill install --dir /tmp/skills` runs
- **THEN** `/tmp/skills/fw/SKILL.md` is written and no agent directory is touched

#### Scenario: Re-run overwrites
- **WHEN** `fw skill install --dir /tmp/skills` runs twice
- **THEN** the file exists once, its content equals the packaged skill, and the exit code is 0 both times

#### Scenario: Nothing detected
- **WHEN** `fw skill install` runs and no agent home directory exists
- **THEN** nothing is written, the message names `--agent` and `--dir`, and the exit code is 4

#### Scenario: Unknown agent
- **WHEN** `fw skill install --agent cursor` runs
- **THEN** nothing is written and the exit code is 2

### Requirement: Skill commands work without a context
The `skill` commands SHALL succeed whether or not a context is initialized, and SHALL not create, read, or append to any event log.

#### Scenario: Install before init
- **WHEN** `fw skill install --dir /tmp/skills` runs on a machine with no context
- **THEN** the exit code is 0 and no `events.jsonl` exists afterwards
