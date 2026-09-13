## 1. Package skeleton

- [x] 1.1 Run `git init` in the project root and verify `.git/` exists. No commit yet; the gate does not exist.
- [x] 1.2 Run `uv init --package --name attention-firewall --build-backend uv .` and verify `pyproject.toml` and `src/attention_firewall/__init__.py` exist with `uv_build` as the build backend.
- [x] 1.3 Edit `pyproject.toml`: set `requires-python = ">=3.12"`, version `0.1.0`, and `[project.scripts] fw = "attention_firewall.cli:main"`. Verify with `uv run python -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['project']['scripts'])"`.
- [x] 1.4 Add dev dependencies with `uv add --dev ruff pytest pytest-cov pre-commit detect-secrets` and verify `uv.lock` exists and `uv sync --locked` succeeds.
- [x] 1.5 Add `[tool.ruff]` (line length 100, `select = ["E","F","I","UP","B"]`) and `[tool.pytest.ini_options]` with `addopts = "--cov=attention_firewall --cov-fail-under=70"` and `testpaths = ["tests"]`. Verify `uv run ruff check .` and `uv run pytest` both run without config errors (pytest may report no tests yet).
- [x] 1.6 Write `src/attention_firewall/cli.py` with a `main()` using stdlib `argparse` that supports `--version`, reading the version via `importlib.metadata.version("attention-firewall")`. Verify `uv run fw --version` prints `0.1.0` and exits 0.
- [x] 1.7 Write `tests/test_cli.py` asserting `fw --version` exits 0 and prints the packaged version. Verify `uv run pytest` passes with coverage at or above 70%.
- [x] 1.8 Quality gate: `uv run ruff check . && uv run ruff format --check .` and `uv run pytest --cov --cov-fail-under=70` both pass. (pre-commit is not configured yet; it is added in group 2.)

## 2. Pre-commit gate

- [x] 2.1 Write `.pre-commit-config.yaml` with `repo: local` hooks that call `uv run ruff check --fix`, `uv run ruff format`, `uv run pytest`, and `uv run detect-secrets-hook --baseline .secrets.baseline`. Verify `uv run pre-commit validate-config` passes.
- [x] 2.2 Generate the baseline with `uv run detect-secrets scan > .secrets.baseline` and verify the file is valid JSON with `python3 -c "import json;json.load(open('.secrets.baseline'))"`.
- [x] 2.3 Add `.gitignore` for `.venv/`, `__pycache__/`, `.pytest_cache/`, `.coverage`, `dist/`. Verify `git status` does not list `.venv/`.
- [x] 2.4 Install hooks with `uv run pre-commit install` and verify `.git/hooks/pre-commit` exists.
- [x] 2.5 Quality gate: `uv run pre-commit run --all-files` passes on the whole tree, then make the first commit with `git commit` (no `--no-verify`) and verify the hooks ran and the commit exists in `git log`.

## 3. GitHub Actions

- [x] 3.1 Write `.github/workflows/ci.yml`: on `push` and `pull_request`, checkout, `astral-sh/setup-uv` pinned to a full commit SHA, `uv sync --locked`, `uv run pre-commit run --all-files`. Verify the YAML parses with `python3 -c "import yaml;yaml.safe_load(open('.github/workflows/ci.yml'))"` and every `uses:` line ends in a 40-character SHA with a `# vX.Y.Z` comment.
- [x] 3.2 Write `.github/workflows/release.yml`: on tags `v*`, `permissions: id-token: write`, a guard step that fails unless the tag equals `v` plus the pyproject version, `uv build`, then `pypa/gh-action-pypi-publish` pinned to a SHA. Verify YAML parses and all actions are SHA-pinned.
- [x] 3.3 Write `.github/dependabot.yml` for ecosystems `uv` and `github-actions`, weekly. Verify YAML parses.
- [x] 3.4 Write `.github/workflows/dependabot-automerge.yml`: on `pull_request` from `dependabot[bot]`, `dependabot/fetch-metadata` pinned to a SHA, and run `gh pr merge --auto --squash` only when `ghsa-id != ''` and `update-type == 'version-update:semver-patch'`. Verify YAML parses and the condition appears verbatim.
- [ ] 3.5 Quality gate: `uv run pre-commit run --all-files` passes, commit the workflows, and verify the commit exists in `git log`.

## 4. README

- [ ] 4.1 Write `README.md` with the one-line install `uv tool install attention-firewall`, the one-paragraph purpose from AGENTS.md, and contributor setup (`uv sync --locked`, `uv run pre-commit install`). Verify the file exists and every command in it has been run once in this session.
- [ ] 4.2 Quality gate: `uv run pre-commit run --all-files` passes, commit, verify in `git log`.

## 5. Remote repository and verification

- [ ] 5.1 Create the public GitHub repository under the authenticated account with `gh repo create attention-firewall --public --source . --push` and verify `git remote -v` shows it and `gh run list` shows a CI run.
- [ ] 5.2 Verify the CI run is green with `gh run watch` or `gh run list --limit 1`. If it fails, fix the cause in the repository, never by loosening a hook.
- [ ] 5.3 Enable "Allow auto-merge" with `gh repo edit --enable-auto-merge` and verify with `gh repo view --json autoMergeAllowed`.
- [ ] 5.4 Add a branch protection rule on the default branch requiring the CI check to pass before merge, via `gh api` on `repos/{owner}/{repo}/branches/{branch}/protection`. Verify with `gh api` that `required_status_checks` lists the CI job.
- [ ] 5.5 Maintainer action, outside the repository: register the GitHub repository as a trusted publisher for the `attention-firewall` project on PyPI. Verify by pushing tag `v0.1.0` and confirming the release workflow publishes. Until this is done the release job is expected to fail at the publish step, and that is acceptable.
- [ ] 5.6 Quality gate: `uv run pre-commit run --all-files` passes locally and the latest CI run on the default branch is green.
