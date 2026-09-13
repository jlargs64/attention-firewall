# attention-firewall

`attention-firewall` (CLI: `fw`) is an open-source, local-first tool that helps
one knowledge worker measure and protect their bandwidth. It is inspired by
Cal Newport's *Slow Productivity* and implements his pull-based, two-column
project management style: a hard-capped **Active** column of slots for the
things you are actually working on, and a **Holding** column for everything
else that has been asked of you. Work is pulled into an active slot when one
opens. It is never pushed in by whoever asked loudest. The tool exists for the
people who get invited onto every project and need an honest number to answer
"when can you take this?" with a date instead of a yes.

## Install

```sh
uv tool install attention-firewall
fw --version
```

## Contributing

The project uses [uv](https://docs.astral.sh/uv/) for everything. Never `pip`.

```sh
uv sync --locked
uv run pre-commit install
```

Every commit runs ruff, pytest (with a 70% coverage floor), and detect-secrets
through pre-commit. CI runs the same hooks. See `AGENTS.md` for the full rules
of engagement.
