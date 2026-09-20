import re
from pathlib import Path

import pytest

from attention_firewall import skill
from attention_firewall.ledger import NotFound, UsageError

REPO_COPY = Path(__file__).parents[1] / "skills" / "fw" / "SKILL.md"


def frontmatter_and_body(text: str) -> tuple[dict[str, str], str]:
    _, front, body = text.split("---\n", 2)
    meta = dict(line.split(": ", 1) for line in front.splitlines())
    return meta, body


# --- skill file ---------------------------------------------------------------


def test_frontmatter_is_valid() -> None:
    meta, _ = frontmatter_and_body(skill.text())
    assert meta["name"] == "fw"
    assert 1 <= len(meta["description"]) <= 1024


def test_body_states_the_rules_and_exit_codes() -> None:
    _, body = frontmatter_and_body(skill.text())
    assert body.count("\n") < 100
    for needle in ("--json", "--actor agent:", "--human-allowed", "fw --help", "events.jsonl"):
        assert needle in body
    for code in range(6):
        assert re.search(rf"^\| {code} \| \S", body, re.M), f"exit code {code} missing"


def test_packaged_copy_matches_repository_copy() -> None:
    packaged = skill.text().encode("utf-8")
    assert packaged == REPO_COPY.read_bytes()


# --- install ------------------------------------------------------------------


@pytest.fixture
def home(tmp_path: Path) -> Path:
    return tmp_path / "home"


@pytest.fixture
def cwd(tmp_path: Path) -> Path:
    return tmp_path / "project"


def test_detected_agents(home: Path, cwd: Path) -> None:
    (home / ".pi" / "agent").mkdir(parents=True)
    (home / ".claude").mkdir()
    written = skill.install([], False, None, home, cwd)
    assert sorted(written) == sorted(
        [home / ".pi/agent/skills/fw/SKILL.md", home / ".claude/skills/fw/SKILL.md"]
    )
    assert not (home / ".codex").exists()
    assert not (home / ".config").exists()
    assert not cwd.exists()


def test_named_agent_project_scope(home: Path, cwd: Path) -> None:
    written = skill.install(["opencode"], True, None, home, cwd)
    assert written == [cwd / ".agents/skills/fw/SKILL.md"]
    assert written[0].read_text() == skill.text()
    assert not home.exists()


def test_shared_project_path_is_written_once(home: Path, cwd: Path) -> None:
    written = skill.install(["opencode", "codex"], True, None, home, cwd)
    assert written == [cwd / ".agents/skills/fw/SKILL.md"]


def test_explicit_dir_rerun_overwrites(home: Path, cwd: Path, tmp_path: Path) -> None:
    target = tmp_path / "skills"
    (home / ".claude").mkdir(parents=True)
    first = skill.install([], False, target, home, cwd)
    (target / "fw" / "SKILL.md").write_text("stale")
    second = skill.install([], False, target, home, cwd)
    assert first == second == [target / "fw" / "SKILL.md"]
    assert first[0].read_text() == skill.text()
    assert not (home / ".claude" / "skills").exists()


def test_nothing_detected(home: Path, cwd: Path) -> None:
    home.mkdir()
    with pytest.raises(NotFound, match="--agent NAME.*--dir PATH"):
        skill.install([], False, None, home, cwd)
    assert list(home.iterdir()) == []


def test_unknown_agent(home: Path, cwd: Path) -> None:
    with pytest.raises(UsageError, match="cursor"):
        skill.install(["cursor"], False, None, home, cwd)
    assert not home.exists() and not cwd.exists()
