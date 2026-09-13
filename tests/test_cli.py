import subprocess
from importlib.metadata import version

import pytest

from attention_firewall.cli import main


def test_version_flag_exits_zero_and_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == version("attention-firewall")


def test_fw_console_script() -> None:
    result = subprocess.run(["fw", "--version"], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "0.1.0"
