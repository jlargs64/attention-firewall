## 1. Skill file

- [x] 1.1 Create branch `agent-skill` from `main` (after the core-bandwidth PR has merged, or from `core-bandwidth` if not) and verify `git branch --show-current` prints it. No new dependencies; `pyproject.toml` `dependencies` stays `[]`.
- [x] 1.2 Write `src/attention_firewall/skills/fw/SKILL.md` per the `agent-skill` spec's "Skill file format" requirement and copy it to `skills/fw/SKILL.md`. Verify with `tests/test_skill.py`: frontmatter `name` is `fw`, `description` is 1 to 1024 characters, body is under 100 lines, body mentions `--json`, `--actor agent:`, `--human-allowed`, `fw --help`, `events.jsonl`, and exit codes 0 through 5, and the two copies are byte-identical.
- [x] 1.3 Verify the wheel carries the skill: `uv build && unzip -l dist/*.whl | grep skills/fw/SKILL.md`. If absent, configure uv_build to include it and repeat. Add a test that reads the skill through `importlib.resources` and compares it to the repository copy.
- [x] 1.4 Quality gate: `uv run ruff check . && uv run ruff format --check .`, `uv run pytest --cov --cov-fail-under=70`, and `uv run pre-commit run --all-files` all pass.

## 2. Skill commands

- [x] 2.1 Add `src/attention_firewall/skill.py` with the `AGENTS` table from the spec, `text() -> str` reading the packaged skill, and `install(agents, project, dir, home, cwd) -> list[Path]` implementing precedence `--dir`, then `--agent`, then detection, raising `UsageError` for an unknown agent and `NotFound` when nothing is detected. Verify with `tests/test_skill.py` using a `tmp_path` home for: detected agents, named agent with project scope, explicit dir, re-run overwrites, nothing detected, unknown agent.
- [x] 2.2 Add `skill show` and `skill install` subparsers to `cli.py` with `--agent` (repeatable, choices from the table), `--project`, and `--dir PATH`; text and `--json` output per the spec. Verify in `tests/test_cli.py`: `fw --help` lists `skill`, `fw skill --help` lists `show` and `install`, `skill show --json` returns `{"ok": true, "skill": ...}`, `skill install --agent cursor` exits 2 with and without `--json`, nothing detected exits 4, and both commands succeed with no context and leave no `events.jsonl` behind.
- [x] 2.3 Quality gate: `uv run ruff check . && uv run ruff format --check .`, `uv run pytest --cov --cov-fail-under=70`, and `uv run pre-commit run --all-files` all pass.

## 3. Docs and PR

- [x] 3.1 Add an "Install the skill" paragraph to the README's "Calling fw from an agent" section covering `fw skill install`, `--project`, `--dir`, and `npx skills add <owner>/attention-firewall`. Verify by running the documented `fw skill install --dir` command against a scratch directory.
- [x] 3.2 Open a pull request from `agent-skill` to `main` with the proposal's "Security and privacy" section in the description and verify the `gate` check is green. Do not merge; the maintainer reviews.
- [x] 3.3 Quality gate: `uv run ruff check . && uv run ruff format --check .`, `uv run pytest --cov --cov-fail-under=70`, and `uv run pre-commit run --all-files` all pass.
