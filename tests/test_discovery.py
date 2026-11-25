from pathlib import Path

import pytest

from dbt_macro_test.discovery import (
    ProfilesChoice,
    ProjectNotFoundError,
    find_project_root,
    resolve_profiles_dir,
    resolve_project_root,
)


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


def test_an_explicit_project_is_used_even_when_the_start_is_somewhere_else(tmp_path: Path) -> None:
    project = tmp_path / "shop"
    project.mkdir()
    (project / "dbt_project.yml").write_text("name: shop\n")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    assert resolve_project_root(project, elsewhere) == project.resolve()


def test_an_explicit_project_without_a_project_file_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ProjectNotFoundError, match="no dbt_project.yml in"):
        resolve_project_root(tmp_path, tmp_path)


def test_without_an_explicit_project_the_nearest_one_is_found(tmp_path: Path) -> None:
    (tmp_path / "dbt_project.yml").write_text("name: x\n")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    assert resolve_project_root(None, nested) == tmp_path.resolve()


def test_the_profiles_flag_beats_everything(tmp_path: Path) -> None:
    (tmp_path / "profiles.yml").write_text("x: {}\n")
    flag = tmp_path / "flag"

    choice = resolve_profiles_dir(flag, tmp_path, {"DBT_PROFILES_DIR": "/somewhere"})

    assert choice == ProfilesChoice(flag, "--profiles-dir")


def test_the_environment_variable_beats_the_projects_own_profiles(tmp_path: Path) -> None:
    (tmp_path / "profiles.yml").write_text("x: {}\n")

    choice = resolve_profiles_dir(None, tmp_path, {"DBT_PROFILES_DIR": "/somewhere"})

    assert choice == ProfilesChoice(None, "DBT_PROFILES_DIR")


def test_the_projects_own_profiles_come_next(tmp_path: Path) -> None:
    (tmp_path / "profiles.yml").write_text("x: {}\n")

    assert resolve_profiles_dir(None, tmp_path, {}) == ProfilesChoice(tmp_path, "the project")


def test_otherwise_dbts_own_default_is_left_to_dbt(tmp_path: Path) -> None:
    assert resolve_profiles_dir(None, tmp_path, {}) == ProfilesChoice(
        None, "dbt's default location"
    )
    assert resolve_profiles_dir(None, tmp_path, {"DBT_PROFILES_DIR": ""}) == ProfilesChoice(
        None, "dbt's default location"
    )
