## Context

See proposal.md for motivation. The CLI is already agent-shaped; this change adds discovery. Constraints: stdlib only, no daemon, no network, the skill must work before `fw init`, and the same text must reach agents through two routes (`fw skill install` and `npx skills add`). The Agent Skills format requires `name` to match the parent directory, so the file lives at `<something>/fw/SKILL.md` everywhere. Vercel's skills CLI scans `skills/<name>/SKILL.md` at the repository root and agent directories, not `src/`, so the repository needs its own copy.

## Goals / Non-Goals

**Goals:**
- One skill text, two delivery routes, zero drift between them.
- A skill short enough that a small local model follows it. Rules, not documentation.
- Installing is one command with no arguments on a normal machine.

**Non-Goals:**
- Parsing or validating agent config files. Detection is "does the agent's home directory exist".
- Uninstall. Deleting one file by hand is fine.
- Keeping the skill in sync for agents installed after `fw skill install` ran. Re-run it.

## Decisions

**The packaged file is the source of truth; the repository copy is a mirror guarded by a test.**
`src/attention_firewall/skills/fw/SKILL.md` ships in the wheel. `skills/fw/SKILL.md` at the repository root exists only so `npx skills add` finds it. `tests/test_skill.py` asserts the two are byte-identical, so a change to one without the other fails pre-commit. Alternatives: a symlink (breaks on Windows checkouts and is not followed by every downloader); a build step that copies the file (a build step for one file). `# ponytail: two copies and one equality test, add a generator if a third copy ever appears`.

**Read the skill with `importlib.resources`, not a path relative to `__file__`.**
`files("attention_firewall") / "skills" / "fw" / "SKILL.md"` works from a wheel, an editable install, and a zip. uv_build includes non-Python files inside the module directory, so no `pyproject.toml` change is expected; task 1.2 verifies this by listing the built wheel and adjusts if wrong.

**Agent table is a dict in `skill.py`.**
`AGENTS = {name: (detect_dir, user_dir, project_dir)}` with the four rows from the spec. Paths are relative to a `home` and `cwd` passed in as parameters so tests use `tmp_path` instead of touching the real home directory. Alternative: read each agent's config to find custom skill paths. Rejected; the escape hatch is `--dir`.

**`skill` runners bypass the ledger entirely.**
The existing `main` resolves a context path for every command but does not touch disk until a command reads the log. `run_skill_show` and `run_skill_install` ignore the context argument and never call `commands._load`. This is why they work before `fw init` and why they cannot leak anything from a context.

**Install writes with `write_bytes` after `mkdir(parents=True, exist_ok=True)`.**
Overwrite is the intended behaviour: upgrading `fw` and re-running `install` is how the skill gets refreshed. No version check, no prompt.

**Skill content decisions.**
The body is a short list of rules plus the exit code table, and it tells the agent to run `fw --help` for command details rather than repeating them. Two reasons: the help text is generated from the parser and cannot drift, and a small model does better with five rules than five pages. The human-only rule is phrased as "only when the human asked for that specific action in this conversation", which is what `--human-allowed` is meant to record.

**Where decisions live.**
No language model runs in this change, so nothing lives in a prompt. State-changing decisions stay in `graph.py`. The skill is text the agent reads; `fw` never interprets it. Provider access: none. Offline: the whole change is offline. Capsules: none are read, so no stale or malformed capsule can occur.

## Risks / Trade-offs

- [Agent directory conventions change] → The table is four lines; update it and release a patch. `--dir` covers the gap in the meantime.
- [A user's agent lives somewhere the table does not know] → Detection finds nothing, exit 4 names `--agent` and `--dir`.
- [The two skill copies drift] → Equality test fails pre-commit and CI.
- [Skill text becomes long and a small model ignores half of it] → Spec caps the body at 100 lines; the test enforces it.
- [Agent ignores the human-only rule and passes `--human-allowed` anyway] → Known and documented in the core-bandwidth proposal. The log records it. Not a control.

## Migration Plan

Additive. Existing contexts and commands are unchanged. Rollback is removing the `skill` subparser and the two files; installed `SKILL.md` copies on user machines are inert without `fw`.

## Open Questions

- Whether to publish the skill to a registry such as skills.sh in addition to the repository path. Deferrable; the repository copy already satisfies `npx skills add <owner>/<repo>`.
