from pathlib import Path

import yaml

from dbt_macro_test.project import installed_packages_dir, with_absolute_local_paths


def project_with_packages_yml(root: Path) -> None:
    (root / "packages.yml").write_text("packages: []\n")


def test_installed_packages_are_found_in_the_default_directory(tmp_path: Path) -> None:
    project_with_packages_yml(tmp_path)
    (tmp_path / "dbt_packages" / "dbt_utils").mkdir(parents=True)

    assert installed_packages_dir({}, tmp_path) == (tmp_path / "dbt_packages").resolve()


def test_the_projects_own_install_path_is_the_one_looked_at(tmp_path: Path) -> None:
    project_with_packages_yml(tmp_path)
    (tmp_path / "vendored" / "dbt_utils").mkdir(parents=True)
    (tmp_path / "dbt_packages" / "other").mkdir(parents=True)

    found = installed_packages_dir({"packages-install-path": "vendored"}, tmp_path)

    assert found == (tmp_path / "vendored").resolve()


def test_nothing_is_reused_when_nothing_is_installed(tmp_path: Path) -> None:
    project_with_packages_yml(tmp_path)

    assert installed_packages_dir({}, tmp_path) is None
    (tmp_path / "dbt_packages").mkdir()
    assert installed_packages_dir({}, tmp_path) is None


def test_a_leftover_directory_is_not_reused_without_a_packages_yml(tmp_path: Path) -> None:
    (tmp_path / "dbt_packages" / "dbt_utils").mkdir(parents=True)

    assert installed_packages_dir({}, tmp_path) is None


def test_relative_local_paths_are_made_absolute(tmp_path: Path) -> None:
    text = "packages:\n  - local: ../shared\n  - package: dbt-labs/dbt_utils\n    version: 1.0.0\n"

    packages = yaml.safe_load(with_absolute_local_paths(text, tmp_path))["packages"]

    assert packages[0] == {"local": str((tmp_path / "../shared").resolve())}
    assert packages[1] == {"package": "dbt-labs/dbt_utils", "version": "1.0.0"}


def test_an_absolute_local_path_is_left_alone(tmp_path: Path) -> None:
    text = f"packages:\n  - local: {tmp_path}/shared\n"

    assert with_absolute_local_paths(text, tmp_path) == text


def test_text_with_nothing_to_change_is_returned_as_it_was(tmp_path: Path) -> None:
    text = "# pinned\npackages:\n  - package: dbt-labs/dbt_utils\n    version: 1.0.0\n"

    assert with_absolute_local_paths(text, tmp_path) == text


def test_text_that_is_not_plain_yaml_is_returned_untouched(tmp_path: Path) -> None:
    text = "packages:\n  - local: {{ env_var('SHARED') }}\n"

    assert with_absolute_local_paths(text, tmp_path) == text
