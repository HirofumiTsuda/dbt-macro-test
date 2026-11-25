import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / ".github" / "scripts" / "ci_scope.sh"

# The rule is the same everywhere, and the script runs in CI under `shell: bash`, which is Git Bash
# on Windows; the `bash` a test finds there may be another one (WSL's), so the rule is tested on
# the systems where `bash` is bash.
pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="the rule is tested where bash is bash"
)


def git(directory: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=directory,
        check=True,
        capture_output=True,
    )


def merged(directory: Path, files: list[str]) -> None:
    """A repository at the state of a pull request's checkout: a merge commit of `files` added
    on a branch into a base that has moved on since the branch was made."""
    git(directory, "init", "-q", "-b", "main")
    (directory / "base.txt").write_text("base")
    git(directory, "add", ".")
    git(directory, "commit", "-q", "-m", "base")
    git(directory, "switch", "-q", "-c", "topic")
    for name in files:
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")
    git(directory, "add", ".")
    git(directory, "commit", "-q", "-m", "topic")
    git(directory, "switch", "-q", "main")
    (directory / "later.txt").write_text("the base moved")
    git(directory, "add", ".")
    git(directory, "commit", "-q", "-m", "later")
    git(directory, "merge", "-q", "--no-ff", "-m", "merge", "topic")


def decision(directory: Path, event: str = "pull_request") -> str:
    output = directory / "github_output"
    environment = {
        **os.environ,
        "GITHUB_EVENT_NAME": event,
        "GITHUB_OUTPUT": str(output),
    }
    ran = subprocess.run(
        ["bash", str(SCRIPT)], cwd=directory, env=environment, capture_output=True, text=True
    )
    assert ran.returncode == 0, ran.stderr
    return output.read_text().strip()


@pytest.mark.parametrize(
    "files",
    [
        ["README.md"],
        ["docs/spec.md", "docs/history/design-log.md"],
        ["docs/example.yml"],  # anything under docs/ is documentation
        ["CHANGELOG.md", "LICENSE"],
        [".github/PULL_REQUEST_TEMPLATE.md"],
        ["README.md", "docs/releasing.md"],
    ],
)
def test_a_change_of_documentation_only_skips_the_suite(tmp_path: Path, files: list[str]) -> None:
    merged(tmp_path, files)

    assert decision(tmp_path) == "code=false"


@pytest.mark.parametrize(
    "files",
    [
        ["src/dbt_macro_test/cli.py"],
        ["tests/test_spec.py"],
        ["pyproject.toml"],
        ["uv.lock"],
        [".github/workflows/ci.yml"],
        [".github/scripts/ci_scope.sh"],
        ["README.md", "src/dbt_macro_test/cli.py"],
        ["tests/fixtures/project/README.md"],
        ["docs.md/x.py"],
    ],
)
def test_anything_else_runs_everything(tmp_path: Path, files: list[str]) -> None:
    merged(tmp_path, files)

    assert decision(tmp_path) == "code=true"


def test_what_the_base_gained_since_is_not_counted_as_part_of_the_change(tmp_path: Path) -> None:
    merged(tmp_path, ["README.md"])  # base.txt and later.txt are not documentation

    assert decision(tmp_path) == "code=false"


def test_a_push_runs_everything_even_when_only_documentation_changed(tmp_path: Path) -> None:
    merged(tmp_path, ["README.md"])

    assert decision(tmp_path, event="push") == "code=true"


def test_when_the_changed_files_cannot_be_read_everything_runs(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "README.md").write_text("x")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "one commit, no parent")

    assert decision(tmp_path) == "code=true"
