"""The spec's story, walked through `main(argv)` against a temp context."""

import csv
import json
from pathlib import Path

import pytest

from attention_firewall.cli import main
from attention_firewall.ledger import LOG_NAME

SEPT_1 = "--now=2026-09-01T00:00:00Z"
SEPT_5 = "--now=2026-09-05T00:00:00Z"
SEPT_10 = "--now=2026-09-10T00:00:00Z"


class Fw:
    def __init__(self, ctx: Path, capsys: pytest.CaptureFixture[str]) -> None:
        self.ctx = ctx
        self.capsys = capsys

    def __call__(self, *argv: str, now: str = SEPT_1) -> dict:
        """Run with --json and return the parsed object; refusals return the stderr object."""
        try:
            main(["--context", str(self.ctx), now, "--json", *argv])
            code = 0
        except SystemExit as exc:
            code = exc.code
        out, err = self.capsys.readouterr()
        body = json.loads(out or err)
        assert body["ok"] == (code == 0)
        if code:
            assert out == ""
            assert body["code"] == code
        return body

    def log_bytes(self) -> bytes:
        return (self.ctx / LOG_NAME).read_bytes()


def test_story(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fw = Fw(tmp_path / "work", capsys)

    # init, two missions, four items
    assert fw("init")["event"]["slot_cap"] == 3
    fw("mission", "add", "ship-fw", "--title", "Ship attention-firewall 1.0")
    fw("mission", "add", "hire", "--title", "Hire a second engineer")
    for title, mission in [
        ("one", "ship-fw"),
        ("two", None),
        ("three", "hire"),
        ("four", "ship-fw"),
    ]:
        argv = ["add", title] + (["--mission", mission] if mission else [])
        assert fw(*argv)["event"]["mission"] == mission
    assert fw("pull", "2", "--until", "2026-09-20")["code"] == 3  # unmapped
    fw("map", "2", "ship-fw")

    # pull three
    fw("pull", "1", "--until", "2026-10-01")
    fw("pull", "2", "--until", "2026-09-20")
    fw("pull", "3", "--until", "2026-11-15")
    status = fw("status")
    assert (status["slots_used"], status["slots_free"], status["next_open"]) == (3, 0, "2026-09-20")

    # refused fourth pull writes nothing
    before = fw.log_bytes()
    refusal = fw("pull", "4", "--until", "2026-10-01")
    assert refusal["code"] == 3
    assert "full" in refusal["message"]
    assert fw.log_bytes() == before

    # wait frees a slot
    fw("wait", "1", now=SEPT_5)
    assert fw("status", now=SEPT_5)["slots_free"] == 1

    # agent pull refused, then allowed with --human-allowed
    refusal = fw("pull", "4", "--until", "2026-10-15", "--actor", "agent:claude", now=SEPT_5)
    assert refusal["code"] == 3
    assert "requires a human" in refusal["message"]
    event = fw(
        "pull",
        "4",
        "--until",
        "2026-10-15",
        "--actor",
        "agent:claude",
        "--human-allowed",
        now=SEPT_5,
    )["event"]
    assert (event["actor"], event["human_allowed"]) == ("agent:claude", True)

    # resume from waiting into a full column is refused
    assert fw("resume", "1", now=SEPT_5)["code"] == 3

    # override past the cap
    fw("add", "five", "--mission", "hire", now=SEPT_5)
    fw("override", "5", "--until", "2026-12-01", now=SEPT_5)
    status = fw("status", now=SEPT_5)
    assert (status["slots_used"], status["slot_cap"], status["slots_free"]) == (4, 3, 0)

    # stall after a --now jump: items last touched on Sept 1 stall, Sept 5 ones do not
    status = fw("status", now=SEPT_10)
    states = {i["id"]: i["state"] for i in status["active"]}
    assert states == {2: "stalled", 3: "stalled", 4: "active", 5: "active"}
    stalls = [e for e in fw("log", now=SEPT_10)["events"] if e.get("edge") == "stall"]
    assert [(e["id"], e["actor"], e["ts"]) for e in stalls] == [
        (2, "system", "2026-09-10T00:00:00Z"),
        (3, "system", "2026-09-10T00:00:00Z"),
    ]
    assert status["next_open"] == "2026-09-20"  # earliest until among occupied items
    assert status["waiting"] == 1

    # export both formats; the log is untouched
    before = fw.log_bytes()
    fw("export", "--format", "jsonl", "--out", str(tmp_path / "fw.jsonl"), now=SEPT_10)
    fw("export", "--format", "csv", "--out", str(tmp_path / "fw.csv"), now=SEPT_10)
    assert (tmp_path / "fw.jsonl").read_bytes() == before
    with (tmp_path / "fw.csv").open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 5
    assert rows[4] == {
        "id": "5",
        "title": "five",
        "mission": "hire",
        "state": "active",
        "created": "2026-09-05T00:00:00Z",
        "last_event": "2026-09-05T00:00:00Z",
        "until": "2026-12-01",
        "overrides": "1",
    }
    assert fw.log_bytes() == before

    # two contexts stay isolated
    personal = Fw(tmp_path / "personal", capsys)
    personal("init")
    status = personal("status")
    assert (status["active"], status["holding"], status["slots_used"]) == ([], [], 0)
    assert len(fw("status", now=SEPT_10)["active"]) == 4


def test_third_override_locks_the_item(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """No edge leads back to holding, so a second and third override cannot be produced through
    the CLI. The extra override events are written by hand to exercise the lock rule."""
    fw = Fw(tmp_path / "work", capsys)
    fw("init")
    fw("mission", "add", "ship-fw")
    fw("add", "one", "--mission", "ship-fw")
    event = fw("override", "1", "--until", "2026-10-01")["event"]
    log = fw.ctx / LOG_NAME
    with log.open("ab") as fh:
        for seq in (5, 6):
            fh.write(json.dumps({**event, "seq": seq}).encode() + b"\n")
    refusal = fw("done", "1")
    assert refusal["code"] == 3
    assert "only delegate or drop remain" in refusal["message"]
    assert fw("drop", "1")["event"]["to"] == "dropped"
