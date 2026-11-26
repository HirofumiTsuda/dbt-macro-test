import re
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from dbt_macro_test.cli import main

pytestmark = pytest.mark.e2e

ROOT = Path(__file__).parent.parent
GUIDE = ROOT / "docs" / "guide.md"
SAMPLE = ROOT / "dev" / "sample_project"
NEEDS_A_PACKAGE = "dbt_utils"  # its example is run by hand, since it needs `dbt deps`


def macro_entries() -> list[str]:
    """The examples of the guide that are whole macro entries of a spec, as text."""
    blocks = re.findall(r"```yaml\n(.*?)```", GUIDE.read_text(), re.S)
    entries = [
        block.removeprefix("macros:\n") if block.startswith("macros:") else block
        for block in blocks
        if block.startswith(("macros:", "  - macro:"))
    ]
    return [e for e in entries if NEEDS_A_PACKAGE not in e]


def test_the_guide_has_examples_to_run() -> None:
    assert len(macro_entries()) >= 8


def test_every_example_of_the_guide_passes_on_the_sample(tmp_path: Path) -> None:
    sample = tmp_path / "sample_project"
    shutil.copytree(SAMPLE, sample, ignore=shutil.ignore_patterns("target", "logs", ".user.yml"))
    for spec in (sample / "macro_test").glob("*.yml"):
        spec.unlink()
    (sample / "macro_test" / "guide.yml").write_text("macros:\n" + "".join(macro_entries()))

    result = CliRunner().invoke(main, ["run", "--project-dir", str(sample)])

    assert result.exit_code == 0, result.output
    assert "failed" not in result.output.splitlines()[-1]
