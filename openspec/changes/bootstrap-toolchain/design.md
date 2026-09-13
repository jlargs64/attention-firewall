## Context

See proposal.md for motivation. Current state: the directory has no code, no `pyproject.toml`, and is not a git repository. Locally, `uv 0.12.13`, `git`, and an authenticated `gh` are installed. `pre-commit` is not installed globally and will run through `uv run`.

Constraints from AGENTS.md that shape this design: uv only, ruff, pytest with a 70% floor, pre-commit is the only commit path, GitHub Actions is the only CI, actions pinned to SHAs, security patches auto-merge and nothing larger does, distribution through `uv tool install`.

This change has no Burr state machine, no model adapter, no capsule, and no offline behavior to design. Those sections of the project's design rules do not apply and are noted here so they are not mistaken for omissions.

## Goals / Non-Goals

**Goals:**
- One definition of the quality gate, in `.pre-commit-config.yaml`, that runs identically on a laptop and in CI.
- Every tool version comes from `uv.lock`. No second copy of a version number anywhere.
- A release path with no long-lived credential in the repository or its secrets.
- The first commit of the repository already passes the gate.

**Non-Goals:**
- Any product behavior. `fw --version` exists only so the package is installable and the smoke test has something to call.
- A documentation site, changelog automation, or multi-platform test matrix.
- Picking the ledger storage. That is `core-ledger`.

## Decisions

**Src layout with `uv_build` as the build backend.**
`src/attention_firewall/` keeps tests from accidentally importing the working directory instead of the installed package. `uv_build` is uv's own backend, needs no extra dependency, and is what `uv init --package` generates. Alternative: hatchling, which is fine but is one more thing in the lockfile for no gain here.

**Static version in `pyproject.toml`, read at runtime with `importlib.metadata`.**
Bumping the version is a one-line edit and a tag. Alternative: derive the version from git tags with `hatch-vcs`. That adds a dependency and makes local builds depend on git state. The release workflow checks that the tag matches the pyproject version and fails if not, so the two cannot drift silently.

**`requires-python = ">=3.12"`, matching the maintainer's interpreter.**
uv requires a value. Users install with `uv tool install`, which resolves and fetches its own interpreter, so the floor rarely matters to them. The maintainer runs 3.12, so the project uses 3.12 features freely and does not carry compatibility code for older versions. Alternative: a lower floor such as 3.10 to widen compatibility. Rejected because nobody is asking for it and it would limit the language features available.

**Pre-commit hooks are `repo: local` and call `uv run <tool>`.**
Ruff, pytest, and detect-secrets all run from the locked environment, so pre-commit, CI, and a developer's terminal execute the same binary at the same version. Alternative: the upstream mirrors such as `astral-sh/ruff-pre-commit`. Those pin their own version in `.pre-commit-config.yaml`, which then drifts from `uv.lock` and gives two places to update.

**Pytest runs at the commit stage, as AGENTS.md requires.**
Trade-off: this will get slow as the suite grows. When a commit takes more than a few seconds, move the pytest hook to `stages: [pre-push]` in a later change. That is a one-line edit and does not change the gate's definition.

**Coverage floor lives in `[tool.pytest.ini_options] addopts` as `--cov --cov-fail-under=70`.**
Every pytest invocation enforces it, including a bare `uv run pytest`. There is no way to run tests without the floor by forgetting a flag.

**CI is one job that runs `uv sync --locked` then `uv run pre-commit run --all-files`.**
The gate is defined once. CI does not repeat ruff and pytest as separate steps, so the two cannot disagree. `setup-uv` is pinned to a commit SHA. Alternative: a matrix over Python versions, rejected because the project does not commit to versions.

**Release by PyPI trusted publishing on tags matching `v*`.**
The job has `permissions: id-token: write`, builds with `uv build`, and publishes with the PyPA publish action pinned to a SHA. No API token exists. A guard step compares the tag to the pyproject version and exits non-zero on mismatch. External requirement: a maintainer registers this repository as a trusted publisher on PyPI once. Until then the job fails at publish, which is the correct behavior.

**Dependabot covers the `uv` and `github-actions` ecosystems weekly.**
A separate workflow uses `dependabot/fetch-metadata` (SHA-pinned) and enables auto-merge only when both `ghsa-id` is non-empty and `update-type` is `version-update:semver-patch`. Everything else stays open for a human. Alternative considered: auto-merge every patch bump to cut PR noise. Rejected because AGENTS.md scopes auto-merge to security patches; widening it is a separate decision. Auto-merge uses `gh pr merge --auto --squash`, which requires the repository setting "Allow auto-merge" and a branch protection rule that requires the CI check. Both are one-time repository settings, listed in tasks.

**detect-secrets with a committed `.secrets.baseline`.**
The baseline is generated before the first commit so the first commit passes. False positives are handled with an inline `# pragma: allowlist secret` comment, never by loosening the hook.

**First commit happens inside the apply of this change.**
`git init`, install hooks, then commit. The commit must pass every hook. If it does not, the gate is wrong and gets fixed before anything else lands.

## Risks / Trade-offs

- [Pytest on every commit becomes slow] → Move the hook to `pre-push` stage in a later change. Gate definition is unchanged.
- [Trusted publisher not yet registered when the first tag is pushed] → Release job fails at the publish step with a clear error. Nothing is published with a fallback token because none exists.
- [Auto-merged security patch breaks something] → CI must pass before auto-merge completes. The merge is a normal commit and can be reverted.
- [Static version and tag drift] → Release guard step fails the job on mismatch.
- [detect-secrets false positive blocks a commit] → Inline allowlist pragma with the reason in the comment.
- [SHA-pinned actions go stale] → Dependabot's `github-actions` ecosystem opens bump PRs. Those are minor or major and wait for review.

## Migration Plan

Greenfield. No migration. Rollback is deleting the generated files; nothing outside the repository changes except the PyPI trusted publisher registration and GitHub repository settings, both of which can be removed by hand.

## Open Questions

- Repository owner and visibility at creation time. Tasks assume the authenticated GitHub account and a public repository, since the project is going open source. Changing either does not change the task list.
