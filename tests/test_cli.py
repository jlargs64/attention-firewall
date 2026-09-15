import json
import subprocess
from importlib.metadata import version
from pathlib import Path

import pytest

from attention_firewall import commands, skill
from attention_firewall.cli import main
from attention_firewall.ledger import LOG_NAME

COMMANDS = [
    "init",
    "mission",
    "add",
    "map",
    "pull",
    "override",
    "done",
    "drop",
    "delegate",
    "wait",
    "resume",
    "status",
    "log",
    "config",
    "export",
    "skill",
]
NOW = "--now=2026-09-01T00:00:00Z"


def run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    try:
        main(argv)
        code = 0
    except SystemExit as exc:
        code = exc.code
    out, err = capsys.readouterr()
    return code, out, err


@pytest.fixture
def seeded(ctx: Path, capsys: pytest.CaptureFixture[str]) -> list[str]:
    """Return the prefix for a context with one mission, item 1 mapped and item 2 not."""
    prefix = ["--context", str(ctx), NOW]
    for argv in (
        ["init"],
        ["mission", "add", "ship-fw", "--title", "Ship"],
        ["add", "one", "--mission", "ship-fw"],
        ["add", "two"],
    ):
        assert run(prefix + argv, capsys)[0] == 0
    return prefix


def test_version_flag_exits_zero_and_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(["--version"], capsys)
    assert code == 0
    assert out.strip() == version("attention-firewall")


def test_fw_console_script() -> None:
    result = subprocess.run(["fw", "--version"], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == version("attention-firewall")


def test_help_names_every_command(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(["--help"], capsys)
    assert code == 0
    for name in COMMANDS:
        assert f"    {name} " in out
    assert run(["mission", "--help"], capsys)[1].count("add") >= 1
    assert "set" in run(["config", "--help"], capsys)[1]
    skill_help = run(["skill", "--help"], capsys)[1]
    assert "show" in skill_help and "install" in skill_help


def test_option_beats_environment(
    seeded: list[str], capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FW_ACTOR", "agent:pi")
    _, out, _ = run(seeded + ["add", "x", "--actor", "human", "--json"], capsys)
    assert json.loads(out)["event"]["actor"] == "human"
    _, out, _ = run(seeded + ["add", "y", "--json"], capsys)
    assert json.loads(out)["event"]["actor"] == "agent:pi"


def test_global_options_work_before_the_command(
    ctx: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _ = run(["--context", str(ctx), "--json", NOW, "init", "--slots", "2"], capsys)
    assert code == 0
    assert json.loads(out)["event"]["slot_cap"] == 2


# --- exit codes -------------------------------------------------------------


def unexpected(*_args, **_kwargs):
    raise RuntimeError("boom")


@pytest.mark.parametrize(
    ("argv", "code"),
    [
        (["status", "--now", "yesterday"], 2),
        (["status", "--actor", "robot"], 2),
        (["status", "--actor", "system"], 2),
        (["config", "set", "slot-cap", "0"], 2),
        (["mission", "add", "Ship FW"], 2),
        (["pull", "1"], 2),
        (["done", "1"], 3),
        (["mission", "add", "ship-fw"], 3),
        (["init"], 3),
        (["pull", "9", "--until", "2026-10-01"], 4),
        (["add", "x", "--mission", "nope"], 4),
        (["map", "1", "nope"], 4),
        (["status", "--context", "/nonexistent/fw"], 4),
    ],
)
def test_exit_codes_with_and_without_json(
    seeded: list[str], capsys: pytest.CaptureFixture[str], argv: list[str], code: int
) -> None:
    ctx = Path(seeded[1])
    before = (ctx / LOG_NAME).read_bytes()
    text_code, text_out, text_err = run(seeded + argv, capsys)
    json_code, json_out, json_err = run(seeded + argv + ["--json"], capsys)
    assert text_code == json_code == code
    assert text_out == json_out == ""
    assert text_err.startswith("fw: ")
    body = json.loads(json_err)
    assert body == {"ok": False, "code": code, "message": body["message"]}
    assert (ctx / LOG_NAME).read_bytes() == before


def test_malformed_ledger_is_exit_5(seeded: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    log = Path(seeded[1]) / LOG_NAME
    log.write_bytes(log.read_bytes() + b'{"seq": 5, "kind": "item_created"\n')
    code, _, err = run(seeded + ["status"], capsys)
    assert code == 5
    assert "line 5" in err
    code, _, err = run(seeded + ["status", "--json"], capsys)
    assert json.loads(err)["code"] == 5


def test_unexpected_error_is_exit_1(
    seeded: list[str], capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(commands, "status", unexpected)
    code, out, err = run(seeded + ["status"], capsys)
    assert (code, out) == (1, "")
    assert "RuntimeError: boom" in err
    code, _, err = run(seeded + ["status", "--json"], capsys)
    assert json.loads(err) == {"ok": False, "code": 1, "message": "RuntimeError: boom"}


# --- output -----------------------------------------------------------------


def test_status_json_keys(seeded: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = run(seeded + ["status", "--json"], capsys)
    assert (code, err) == (0, "")
    body = json.loads(out)
    assert body["ok"] is True
    assert set(body) >= {
        "active",
        "holding",
        "waiting",
        "delegated",
        "slots_used",
        "slot_cap",
        "slots_free",
        "next_open",
    }
    assert out.count("\n") == 1


def test_log_item_json(seeded: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    run(seeded + ["pull", "1", "--until", "2026-10-01"], capsys)
    _, out, _ = run(seeded + ["log", "--item", "1", "--json"], capsys)
    events = json.loads(out)["events"]
    assert [e["id"] for e in events] == [1, 1]
    assert [e["seq"] for e in events] == sorted(e["seq"] for e in events)
    assert [e["kind"] for e in events] == ["item_created", "item_transitioned"]


def test_text_output_for_every_result(
    seeded: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    outputs = {}
    for name, argv in {
        "pull": ["pull", "1", "--until", "2026-10-01"],
        "map": ["map", "2", "ship-fw"],
        "config": ["config", "set", "slot-cap", "4"],
        "missions": ["mission", "list"],
        "status": ["status"],
        "log": ["log", "--limit", "2"],
        "export": ["export", "--format", "jsonl", "--out", seeded[1] + "/../out.jsonl"],
    }.items():
        code, out, err = run(seeded + argv, capsys)
        assert (code, err) == (0, ""), name
        outputs[name] = out
    assert "holding -> active until 2026-10-01" in outputs["pull"]
    assert "mapped to ship-fw" in outputs["map"]
    assert "slot_cap = 4" in outputs["config"]
    assert "ship-fw  Ship  active=1 holding=1" in outputs["missions"]
    assert "Active (1/4 slots, 3 free)" in outputs["status"]
    assert "Next open: 2026-09-01" in outputs["status"]
    assert outputs["log"].count("\n") == 2
    assert outputs["export"].startswith("wrote jsonl to ")


def test_empty_mission_list_text(ctx: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run(["--context", str(ctx), "init"], capsys)
    assert "no missions" in run(["--context", str(ctx), "mission", "list"], capsys)[1]


# --- non-interactive --------------------------------------------------------


def test_pull_with_closed_stdin_matches_direct_call(
    seeded: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    argv = seeded + ["pull", "1", "--until", "2026-10-01", "--json"]
    proc = subprocess.run(
        ["fw", *argv], stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True
    )
    via_subprocess = json.loads(proc.stdout)["event"]
    # Item 1 is now active; drop it and re-add an identical one so the direct call can pull too.
    run(seeded + ["drop", "1"], capsys)
    run(seeded + ["add", "one", "--mission", "ship-fw"], capsys)
    _, out, _ = run(seeded + ["pull", "3", "--until", "2026-10-01", "--json"], capsys)
    direct = json.loads(out)["event"]
    keep = {"edge", "from", "to", "until", "actor", "kind", "ts"}
    assert {k: v for k, v in via_subprocess.items() if k in keep} == {
        k: v for k, v in direct.items() if k in keep
    }


# --- skill: no context needed ------------------------------------------------


@pytest.fixture
def nowhere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Empty HOME, cwd, and context so nothing is detected and nothing is initialized."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FW_CONTEXT", str(tmp_path / "ctx"))
    return tmp_path


def test_skill_show_needs_no_context(nowhere: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = run(["skill", "show"], capsys)
    assert (code, err) == (0, "")
    assert out == skill.text()
    code, out, _ = run(["skill", "show", "--json"], capsys)
    assert code == 0
    assert json.loads(out) == {"ok": True, "skill": skill.text()}
    assert not (nowhere / "ctx").exists()


def test_skill_install_dir_needs_no_context(
    nowhere: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = nowhere / "skills"
    code, out, err = run(["skill", "install", "--dir", str(target)], capsys)
    assert (code, err) == (0, "")
    assert out.strip() == f"wrote {target / 'fw' / 'SKILL.md'}"
    code, out, _ = run(["skill", "install", "--dir", str(target), "--json"], capsys)
    assert json.loads(out) == {"ok": True, "installed": [str(target / "fw" / "SKILL.md")]}
    assert (target / "fw" / "SKILL.md").read_text() == skill.text()
    assert not list(nowhere.rglob(LOG_NAME))


def test_skill_install_detects_home_agents(
    nowhere: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (nowhere / "home" / ".claude").mkdir()
    code, out, _ = run(["skill", "install", "--json"], capsys)
    assert code == 0
    assert json.loads(out)["installed"] == [str(nowhere / "home/.claude/skills/fw/SKILL.md")]
    code, out, _ = run(["skill", "install", "--agent", "pi", "--project", "--json"], capsys)
    assert json.loads(out)["installed"] == [str(nowhere / ".pi/skills/fw/SKILL.md")]


@pytest.mark.parametrize(
    ("argv", "code", "needle"),
    [
        (["skill", "install", "--agent", "cursor"], 2, "cursor"),
        (["skill", "install"], 4, "--agent"),
        (["skill", "install"], 4, "--dir"),
    ],
)
def test_skill_install_errors(
    nowhere: Path, capsys: pytest.CaptureFixture[str], argv: list[str], code: int, needle: str
) -> None:
    text_code, text_out, text_err = run(argv, capsys)
    json_code, json_out, json_err = run(argv + ["--json"], capsys)
    assert text_code == json_code == code
    assert text_out == json_out == ""
    assert needle in text_err and needle in json.loads(json_err)["message"]
    assert json.loads(json_err)["code"] == code
    assert [p for p in nowhere.rglob("*") if p.is_file()] == []
