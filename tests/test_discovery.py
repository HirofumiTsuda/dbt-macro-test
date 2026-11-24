from pathlib import Path

import pytest

from dbt_macro_test.discovery import ProjectNotFoundError, find_project_root


def test_root_is_the_nearest_ancestor_with_a_project_file(tmp_path: Path) -> None:
    (tmp_path / "dbt_project.yml").write_text("name: x\n")
    nested = tmp_path / "macro_test" / "utils"
    nested.mkdir(parents=True)

    assert find_project_root(nested) == tmp_path.resolve()


def test_the_start_directory_itself_can_be_the_root(tmp_path: Path) -> None:
    (tmp_path / "dbt_project.yml").write_text("name: x\n")

    assert find_project_root(tmp_path) == tmp_path.resolve()


def test_missing_project_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ProjectNotFoundError, match="no dbt_project.yml"):
        find_project_root(tmp_path)
