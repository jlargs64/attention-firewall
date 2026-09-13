# AGENTS.md

Rules of engagement for anyone, human or agent, working in this repository.
OpenSpec artifact rules live in `openspec/config.yaml` and are held to the same
standards described here.

## What this project is

`attention-firewall` (CLI: `fw`) is an open-source, local-first tool that helps
one knowledge worker measure and protect their bandwidth. It is inspired by
Cal Newport's *Slow Productivity* and implements his pull-based, two-column
project management style:

- **Active column**: a hard-capped set of slots (the number of things a person
  is actually working on). Newport's default is three.
- **Holding column**: everything that has been asked of the person but not yet
  pulled into an active slot.

Work is *pulled* into an active slot when one opens. It is never *pushed* in by
whoever asked loudest. The tool exists for the people who get invited onto every
project by peers, managers, and executives, and who need an honest number to
answer "when can you take this?" with a date instead of a yes.

Requests arrive as unstructured natural language. An agent built on Apache Burr
organizes them and maps them onto the user's missions, projects, and daily
goals. Burr is chosen to keep the agent deterministic and auditable: the state
machine decides what happens, the language model only fills in classifications
inside it.

The tool must work with any AI provider, but the design center is cheap or free
small language models running on local hardware.

Like `git`, `fw` does nothing until the user initializes it against one or more
GitHub repositories, which act as the ledger.

### Contexts and capsules

A person may run `fw` in several isolated environments (for example a work
laptop and a personal machine). Each is a **context**. Contexts never sync and
there is no daemon. The only thing that crosses between them is a **capsule**:
a small, schema-bounded record of bandwidth (slots used, dates, calendar shape)
that a human copies by hand. The capsule schema has no free-text field, so it
cannot carry a project name, a person's name, or prose. That is the whole
privacy model: schema-bounded, not redacted.

### Design invariants (do not violate without a spec change)

1. The capsule schema has no string field that could carry free text.
2. Work-context data never leaves the work context. Only capsules cross.
3. No background daemon, no automatic sync between contexts.
4. Protected time is a block the tool can display but never allocate.
5. Bandwidth is pull-based. The tool never auto-assigns work into an active
   slot.
6. Provider-agnostic. No code path may require a specific hosted AI vendor.
7. Local-first. The tool must be fully usable offline apart from GitHub access.
8. Every item is in exactly one enumerated state. Every transition, including
   overrides, is an edge in the graph and is recorded. The model produces
   artifacts that feed a transition and never selects one. After more than two
   overrides on one item, the only remaining edges are delegate or drop.
9. The user's data is theirs. Every item and every transition is written to a
   local JSONL file, one event per line, append-only. GitHub Issues is a
   mirror, never the only copy. `fw export` produces plain files that need no
   `fw` to read. No feature may depend on data that exists only in GitHub.

## Toolchain

| Concern | Tool | Notes |
|---|---|---|
| Package manager | `uv` | Never `pip`. `uv add`, `uv sync --locked`, `uv run`. Commit `uv.lock`. |
| Lint and format | `ruff` | `ruff check` and `ruff format`. Configured in `pyproject.toml`. |
| Tests | `pytest` + `pytest-cov` | Coverage floor is 70%. Do not lower it. Do not spend effort raising the number for its own sake. |
| Commit gate | `pre-commit` | Runs ruff, pytest, and secret detection. Every commit goes through it. |
| Secrets | `detect-secrets` (pre-commit hook) | Baseline file committed. |
| CI/CD | GitHub Actions | The only CI system. |
| Dependency updates | Dependabot | Security patch bumps auto-merge. Minor and major bumps wait for a human. |
| Distribution | `uv tool install attention-firewall` | Published to PyPI via GitHub Actions trusted publishing (OIDC, no long-lived tokens). Installing from a GitHub tag also works. |
| Agent framework | Apache Burr | State machine owns control flow. One persisted machine per item, stepped forward with `now` as an input on each run. No daemon. |
| Local record | JSONL | Append-only, one event per line. Chosen over a single JSON document because appends do not rewrite the file and git diffs stay one line per change. |
| Python version | `>=3.12` | Matches the maintainer's interpreter. Use 3.12 features freely; no compatibility code for older versions. Users install via `uv tool install`, which brings its own interpreter, so this is not a support matrix. |

## Rules

### Commits

- Every commit runs through pre-commit. Never use `git commit --no-verify` or
  otherwise skip hooks. If a hook fails, fix the cause.
- Do not commit if `uv run pytest` fails or coverage is below 70%.
- Do not commit secrets, tokens, `.env` files, or real capsule data from a work
  context. If `detect-secrets` flags something real, rotate it.

### Dependencies

- Add with `uv add <pkg>` (or `uv add --dev <pkg>`). Never edit the lockfile by
  hand and never install with `pip`.
- Prefer few, boring dependencies. Every new runtime dependency is a supply
  chain risk that strangers will install on their machines. Justify it in the
  change proposal.
- Pin GitHub Actions to full commit SHAs, not floating tags.
- Dependabot handles version bumps. Patch-level security updates are
  auto-merged once CI passes. Anything with a major or minor bump, or any
  changelog that mentions breaking changes, is left for a maintainer to review.

### Code

- Ruff is the source of truth for style. Do not argue with it; configure it in
  `pyproject.toml` if a rule is wrong for this project.
- Tests live in `tests/` and mirror the package layout. New behavior ships with
  tests in the same change.
- Never call an AI provider directly from business logic. Provider access goes
  through one adapter layer so a local SLM and a hosted model are
  interchangeable.
- Anything that decides state (slot counts, transitions, what is active or
  holding) lives in the Burr state machine, not in a prompt.

### Security posture

- This will run on many machines owned by people we do not know. Assume hostile
  input from the ledger, from pasted capsules, and from model output.
- Capsule import must parse against the schema and fail closed. Anything that
  does not match exactly is rejected, not repaired.
- Treat model output as data to validate, never as instructions to execute.

### OpenSpec

- Every change goes through OpenSpec (`openspec/changes/<name>/`) and is held
  to the same gates as any other work: ruff, pytest with coverage, secret
  detection, and CI green.
- Do not scaffold a change directory by hand. Use `openspec new change`.
- A change is not archived until `openspec-verify-change` passes and the
  tasks that run the quality gates are checked off.
- Any change touching the capsule schema, context isolation, or protected time
  must say so explicitly in its proposal under a **Security and privacy**
  heading.

### Working style for agents

- Read `openspec/specs/` before proposing behavior. If a spec exists, the spec
  wins over your assumption.
- Do not widen scope silently. If a task reveals a needed spec change, stop and
  propose it.
- Deliverable diagrams are produced with the `diagram-design` plugin from
  handoff specs under `diagrams/`. Plain ASCII sketches in conversation are
  fine.
- Prefer deleting code to adding it. This tool's value is in doing less.

## Commands

```bash
uv sync --locked                 # install exactly what the lockfile says
uv run pre-commit install        # one-time: wire the commit gate
uv run pre-commit run --all-files
uv run ruff check . && uv run ruff format --check .
uv run pytest --cov --cov-fail-under=70
```
