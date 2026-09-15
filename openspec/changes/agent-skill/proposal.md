## Why

`fw` was built to be driven by coding agents: `--json`, stable exit codes, no prompts, `--actor agent:<name>`, `--human-allowed`. But nothing tells an agent that `fw` exists or when to reach for it. A person running pi against a homelab model, or Claude Code on a laptop, gets no benefit until the agent is told. Skills are how agents learn about tools. `fw` should ship its own.

## What Changes

- A `SKILL.md` for `fw` in the open Agent Skills format (`name`, `description` frontmatter, markdown body). It states what `fw` is, when to use it, the five rules an agent must follow, and points at `fw --help` for everything else. Short enough for a small local model to hold.
- The skill is packaged inside the wheel so the installed `fw` always carries the skill that matches its version.
- `fw skill show` prints the skill to stdout so it can be piped anywhere.
- `fw skill install` writes the skill into the skill directories of detected agents (Claude Code, pi, opencode, Codex), user-level by default, project-level with `--project`, or to an explicit `--dir`. Idempotent: re-running overwrites the file with the current version.
- A second copy of the skill at `skills/fw/SKILL.md` in the repository so `npx skills add <owner>/attention-firewall` works for people who prefer that route. A test keeps the two copies byte-identical.
- The `skill` commands need no initialized context and read no ledger.
- README gains an "Install the skill" paragraph in the agent section.

## Capabilities

### New Capabilities

- `agent-skill`: the skill file's required content and format, `fw skill show`, `fw skill install`, agent directory detection, and the packaged-copy-equals-repo-copy guarantee.

### Modified Capabilities

- `cli-interface`: the "Command surface" requirement gains `skill show` and `skill install`.
- `event-ledger`: the "Context initialization" requirement's "Command before init" scenario exempts `skill` commands, which need no context.

## Non-goals

- An MCP server. It needs a long-running process and the project has a no-daemon invariant. A skill plus the CLI covers the same ground.
- The Burr intake agent. That is `fw`'s own agent and a separate change. This change is about other people's agents calling `fw`.
- Detecting agents installed in unusual locations. `--dir` is the escape hatch.
- Skill directories for agents beyond the four named. Adding one is a one-line table entry in a later change.

## Security and privacy

This change does not touch the capsule schema, context isolation, or protected time. It writes one markdown file into directories under the user's home or the current project, and only when asked. It reads nothing from any context.

The skill text is instructions to an agent, not code, and it is treated as such: `fw` never executes it. Because the skill is user-installed content in the agent's own directory, the agent already trusts that location. The skill's rules tell agents to record themselves as `agent:<name>` and to add `--human-allowed` only after the human has asked. These are the same honesty-record rules the CLI already has; the skill makes them visible to the agent.

## Pull-based bandwidth

Indirect. The skill teaches agents that only the human pulls work into a slot. Without it, an agent with shell access might treat `fw pull` as just another command. With it, the agent knows to ask first.

## Dependencies

No new runtime dependencies. The skill is read with `importlib.resources`, paths come from `pathlib`, argparse gains one subparser.

## Impact

- New: `src/attention_firewall/skills/fw/SKILL.md`, `skills/fw/SKILL.md`, `src/attention_firewall/skill.py`, `tests/test_skill.py`.
- Changed: `cli.py` (one subparser group), `README.md`, `pyproject.toml` only if uv_build needs to be told to include the markdown file.
- Users of `npx skills` and users of `fw skill install` receive identical content.
