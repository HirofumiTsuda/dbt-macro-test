from pathlib import Path

import pytest

from dbt_macro_test.project import (
    ProfilesChoice,
    ProjectNotFoundError,
    find_project_root,
    resolve_profiles_dir,
    resolve_project_root,
    target_adapter,
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


def write_profiles(directory: Path, text: str) -> None:
    (directory / "profiles.yml").write_text(text)


PROFILES = """
shop:
  target: dev
  outputs:
    dev: {type: duckdb, path: ":memory:"}
    ci: {type: Postgres, host: localhost}
"""


def test_the_adapter_is_the_type_of_the_default_target(tmp_path: Path) -> None:
    write_profiles(tmp_path, PROFILES)

    assert target_adapter(tmp_path, {}, "shop", None) == "duckdb"


def test_the_target_asked_for_wins_and_the_type_is_lower_cased(tmp_path: Path) -> None:
    write_profiles(tmp_path, PROFILES)

    assert target_adapter(tmp_path, {}, "shop", "ci") == "postgres"


def test_without_a_directory_the_environment_variable_is_used(tmp_path: Path) -> None:
    write_profiles(tmp_path, PROFILES)

    assert target_adapter(None, {"DBT_PROFILES_DIR": str(tmp_path)}, "shop", "ci") == "postgres"


@pytest.mark.parametrize(
    "profile, target",
    [("other", None), ("shop", "no_such_target")],
)
def test_the_adapter_is_not_told_for_a_profile_or_target_that_is_not_there(
    tmp_path: Path, profile: str, target: str | None
) -> None:
    write_profiles(tmp_path, PROFILES)

    assert target_adapter(tmp_path, {}, profile, target) is None


def test_the_adapter_is_not_told_without_a_file_or_with_jinja_in_it(tmp_path: Path) -> None:
    assert target_adapter(tmp_path, {}, "shop", None) is None  # no profiles.yml
    write_profiles(
        tmp_path,
        "shop:\n  target: dev\n  outputs:\n    dev: {type: \"{{ env_var('ADAPTER') }}\"}\n",
    )
    assert target_adapter(tmp_path, {}, "shop", None) is None
    write_profiles(tmp_path, "shop: [this, is, not, a, mapping")
    assert target_adapter(tmp_path, {}, "shop", None) is None
