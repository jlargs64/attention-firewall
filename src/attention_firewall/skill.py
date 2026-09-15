"""The packaged agent skill (SKILL.md): read it, install it into agent skill directories."""

from importlib.resources import files
from pathlib import Path

from .ledger import NotFound, UsageError

# agent -> (detected by, user-level skills dir, project-level skills dir).
# The first two are relative to the home directory, the third to the current directory.
AGENTS = {
    "claude-code": (".claude", ".claude/skills", ".claude/skills"),
    "pi": (".pi/agent", ".pi/agent/skills", ".pi/skills"),
    "opencode": (".config/opencode", ".config/opencode/skills", ".agents/skills"),
    "codex": (".codex", ".codex/skills", ".agents/skills"),
}


def text() -> str:
    return (files("attention_firewall") / "skills" / "fw" / "SKILL.md").read_text("utf-8")


def install(
    agents: list[str], project: bool, dir: Path | None, home: Path, cwd: Path
) -> list[Path]:
    """Write SKILL.md to `<dir>/fw/SKILL.md` for each target. Precedence: --dir, --agent,
    then every agent whose home directory exists. Returns the paths written."""
    if dir is not None:
        targets = [dir]
    else:
        if unknown := sorted(set(agents) - AGENTS.keys()):
            raise UsageError(f"unknown agent {', '.join(unknown)}; choose from {', '.join(AGENTS)}")
        names = agents or [n for n, (probe, _, _) in AGENTS.items() if (home / probe).is_dir()]
        if not names:
            raise NotFound("no agent directory found; name one with --agent NAME or use --dir PATH")
        targets = [cwd / AGENTS[n][2] if project else home / AGENTS[n][1] for n in names]
    body = text().encode("utf-8")
    written = []
    for target in dict.fromkeys(targets):  # opencode and codex share a project path
        path = target / "fw" / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        written.append(path)
    return written
