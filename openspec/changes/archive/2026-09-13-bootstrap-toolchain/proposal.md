## Why

AGENTS.md says every change goes through ruff, pytest with coverage, secret detection, pre-commit, and GitHub Actions. None of that exists yet, so no other change can meet its own quality gate. This change builds the gates first so that `core-ledger` and everything after it can be held to them.

## What Changes

- Add `pyproject.toml` managed by uv: package `attention-firewall`, console script `fw`, dev dependency group with ruff, pytest, pytest-cov, pre-commit, and detect-secrets. Commit `uv.lock`.
- Add a minimal `fw` entry point using stdlib `argparse` that only prints its version. It exists so the package is installable and testable end to end, not as product behavior.
- Configure ruff (lint and format) and pytest with pytest-cov in `pyproject.toml`. Coverage floor is 70%.
- Add `.pre-commit-config.yaml` running ruff check, ruff format, pytest with the coverage floor, and detect-secrets with a committed baseline.
- Add GitHub Actions:
  - `ci.yml`: on push and pull request, `uv sync --locked`, then `pre-commit run --all-files`.
  - `release.yml`: on a version tag, build with uv and publish to PyPI using trusted publishing (OIDC). No stored token.
  - `dependabot.yml` for uv and GitHub Actions, plus an auto-merge workflow that merges only patch-level bumps flagged as security updates once CI is green. Minor and major bumps wait for a human.
- Pin every third-party GitHub Action to a full commit SHA.
- Add one smoke test: `fw --version` exits 0 and prints the version from package metadata.
- Add a short README with the install line and the pre-commit setup steps.

## Capabilities

### New Capabilities

None. This change is tooling only. `skip_specs: true` is set in `.openspec.yaml`.

### Modified Capabilities

None.

## Non-goals

- `fw init`, the ledger, the state graph, Burr, any model adapter, capsules, protected time. Each is a later change.
- Choosing between GitHub Issues and a git repo as the mirror target. That decision belongs to `core-ledger`.
- A Python support matrix. `requires-python` is `>=3.12`, the maintainer's interpreter. Users install via `uv tool install`, which brings an interpreter, so older versions are not tested or supported.
- Tuning the coverage number. 70% is the floor and is not revisited here.

## Security and privacy

This change does not touch the capsule schema, context isolation, protected time, or the state graph. It adds the controls that later changes rely on:

- detect-secrets in pre-commit and CI, so a token or a real capsule from a work context cannot be committed by accident.
- Trusted publishing, so there is no long-lived PyPI token anywhere in the repo or its secrets.
- Locked dependency install in CI (`uv sync --locked`) and SHA-pinned actions, so a compromised upstream tag cannot change what CI runs.
- Auto-merge restricted to patch-level security bumps. Anything larger is reviewed by a person.

## Pull-based bandwidth

This change does not relate to pull-based bandwidth. It is the quality gate that later behavior changes pass through.

## Dependencies

New runtime dependencies: none. The entry point uses `argparse` and `importlib.metadata` from the standard library.

Dev-only dependencies: ruff, pytest, pytest-cov, pre-commit, detect-secrets. Each is named in AGENTS.md as part of the required toolchain.

## Impact

- New files: `pyproject.toml`, `uv.lock`, `src/attention_firewall/__init__.py`, `src/attention_firewall/cli.py`, `tests/test_cli.py`, `.pre-commit-config.yaml`, `.secrets.baseline`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.github/workflows/dependabot-automerge.yml`, `.github/dependabot.yml`, `README.md`.
- External setup a maintainer must do once, outside this repo: create the PyPI project and register the GitHub repository as a trusted publisher. The release workflow cannot succeed until that is done.
- The repository is not yet a git repository. `git init` and the first commit happen as part of applying this change, and that first commit must itself pass pre-commit.
