import importlib.util
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location(
    "release_notes", ROOT / ".github" / "scripts" / "release_notes.py"
)
assert _spec is not None and _spec.loader is not None
release_notes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release_notes)

CHANGELOG = """# Changelog

## [Unreleased]

## [0.3.0] - 2026-12-01

Test it on more databases.

### Added

- one thing

### Fixed

- another

## [0.2.0] - 2026-11-26

The second release.

### Added

- an older thing

## [0.1.0] - 2026-11-25

Only highlights, no sections.
"""


def test_the_entry_of_a_version_is_what_is_under_its_heading_up_to_the_next_version() -> None:
    text = release_notes.entry(CHANGELOG, "0.3.0")

    assert text.startswith("Test it on more databases.")
    assert "- another" in text
    assert "older thing" not in text
    assert "## [" not in text


def test_the_entry_of_the_last_version_runs_to_the_end() -> None:
    assert release_notes.entry(CHANGELOG, "0.1.0") == "Only highlights, no sections."


def test_a_version_without_an_entry_is_an_error() -> None:
    with pytest.raises(release_notes.NotesError, match=r"no heading '## \[9\.9\.9\]'"):
        release_notes.entry(CHANGELOG, "9.9.9")


def test_the_version_is_matched_exactly_and_not_as_a_prefix() -> None:
    with pytest.raises(release_notes.NotesError):
        release_notes.entry(CHANGELOG, "0.3")


def test_the_highlights_are_what_comes_before_the_first_section() -> None:
    highlights, sections = release_notes.split_entry(release_notes.entry(CHANGELOG, "0.3.0"))

    assert highlights == "Test it on more databases."
    assert sections.startswith("### Added")
    assert "### Fixed" in sections


def test_the_notes_are_the_highlights_the_sections_the_install_line_and_the_links() -> None:
    text = release_notes.notes(CHANGELOG, "0.3.0", "0.2.0", "me/repo")

    assert text.startswith("Test it on more databases.\n\n## Changes\n\n### Added\n")
    assert "- another" in text
    assert "pip install -U dbt-macro-test==0.3.0" in text
    assert "https://github.com/me/repo/blob/v0.3.0/CHANGELOG.md" in text
    assert "[v0.2.0...v0.3.0](https://github.com/me/repo/compare/v0.2.0...v0.3.0)" in text
    assert "older thing" not in text


def test_without_a_previous_version_there_is_no_link_to_a_comparison() -> None:
    text = release_notes.notes(CHANGELOG, "0.3.0", None, "me/repo")

    assert "compare" not in text
    assert "CHANGELOG" in text


def test_an_entry_with_only_highlights_has_no_changes_heading() -> None:
    text = release_notes.notes(CHANGELOG, "0.1.0", None, "me/repo")

    assert "## Changes" not in text
    assert text.startswith("Only highlights, no sections.")


def test_an_entry_without_highlights_is_an_error_that_says_what_to_write() -> None:
    changelog = "## [0.4.0] - 2026-12-02\n\n### Added\n\n- x\n"

    with pytest.raises(release_notes.NotesError, match="no highlights: write a paragraph"):
        release_notes.notes(changelog, "0.4.0", None, "me/repo")


def test_main_prints_the_notes_and_exits_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "CHANGELOG.md"
    path.write_text(CHANGELOG)

    code = release_notes.main(["0.3.0", "--previous", "0.2.0", "--changelog", str(path)])

    assert code == 0
    assert capsys.readouterr().out.startswith("Test it on more databases.")


def test_main_says_what_is_wrong_as_a_workflow_error_and_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "CHANGELOG.md"
    path.write_text(CHANGELOG)

    code = release_notes.main(["9.9.9", "--changelog", str(path)])

    assert code == 1
    assert capsys.readouterr().err.startswith("::error::CHANGELOG.md has no heading")


def test_the_changelog_of_this_repository_gives_notes_for_the_version_in_pyproject() -> None:
    """What stops a release without highlights before it is published, run on every change."""
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]

    text = release_notes.notes((ROOT / "CHANGELOG.md").read_text(), version, None, "me/repo")

    assert f"pip install -U dbt-macro-test=={version}" in text
