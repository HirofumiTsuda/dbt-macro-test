import re
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from dbt_macro_test.cli import main
from dbt_macro_test.spec import load_specs

pytestmark = pytest.mark.e2e

SAMPLE = Path(__file__).parent.parent / "dev" / "sample_project"
CASES = 18  # change it with the sample: the test fails when a case is added or taken away
HELPERS = {"tax_rate"}  # macros that are there to be overridden, with no case of their own


@pytest.fixture
def sample(tmp_path: Path) -> Path:
    """The sample in a copy, since dbt writes next to the project it is given."""
    copy = tmp_path / "sample_project"
    shutil.copytree(SAMPLE, copy, ignore=shutil.ignore_patterns("target", "logs", ".user.yml"))
    return copy


def test_every_case_of_the_sample_passes(sample: Path) -> None:
    result = CliRunner().invoke(main, ["run", "--project-dir", str(sample)])

    assert result.exit_code == 0, result.output
    assert f"{CASES} passed" in result.output


def test_the_sample_has_the_number_of_cases_that_the_test_knows(sample: Path) -> None:
    result = CliRunner().invoke(main, ["run", "--project-dir", str(sample), "--list"])

    assert result.exit_code == 0, result.output
    assert len(result.output.split()) == CASES


def test_every_macro_of_the_sample_has_a_case_unless_it_is_there_to_be_overridden() -> None:
    defined = {
        name
        for path in (SAMPLE / "macros").glob("*.sql")
        for name in re.findall(r"{%-?\s*macro\s+(\w+)", path.read_text())
    }
    tested = {m.macro for spec in load_specs(SAMPLE / "macro_test") for m in spec.macros}

    assert defined - tested == HELPERS
    assert tested <= defined


def test_every_spec_file_of_the_sample_says_what_it_shows() -> None:
    silent = [
        p.name for p in (SAMPLE / "macro_test").glob("*.yml") if not p.read_text().startswith("#")
    ]

    assert silent == []
