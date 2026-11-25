from pathlib import Path
from typing import Any

import yaml

from dbt_macro_test.generate import (
    build_files,
    carried_over,
    macro_call,
    model_name,
    project_config,
    write_project,
)
from dbt_macro_test.spec import Case, MacroSpec, SpecFile

RAW: dict[str, Any] = {
    "name": "shop",
    "profile": "shop",
    "macro-paths": ["macros", "more"],
    "model-paths": ["models"],
    "seed-paths": ["seeds"],
    "vars": {"country": "JP"},
    "dispatch": [{"macro_namespace": "x", "search_order": ["shop", "x"]}],
    "on-run-start": ["select 1"],
    "on-run-end": ["select 2"],
}


def test_project_config_keeps_settings_that_change_macro_behavior(tmp_path: Path) -> None:
    config = project_config(RAW, tmp_path)

    assert config["name"] == "shop"
    assert config["profile"] == "shop"
    assert config["vars"] == {"country": "JP"}
    assert config["dispatch"] == RAW["dispatch"]


def test_project_config_points_macro_paths_at_the_real_macros(tmp_path: Path) -> None:
    config = project_config(RAW, tmp_path)

    assert config["macro-paths"] == [str(tmp_path / "macros"), str(tmp_path / "more")]
    assert config["model-paths"] == ["models"]
    assert config["seed-paths"] == []


def test_project_config_drops_run_hooks(tmp_path: Path) -> None:
    config = project_config(RAW, tmp_path)

    assert "on-run-start" not in config
    assert "on-run-end" not in config


def test_project_config_does_not_modify_its_input(tmp_path: Path) -> None:
    before = yaml.safe_dump(RAW)

    project_config(RAW, tmp_path)

    assert yaml.safe_dump(RAW) == before


def test_macro_call_passes_arguments_by_name() -> None:
    assert macro_call("safe_divide", {"numerator": 10, "denominator": "x"}) == (
        'safe_divide(numerator=10, denominator="x")'
    )
    assert macro_call("now", {}) == "now()"


def test_model_name_is_unique_per_spec_file_macro_and_case(tmp_path: Path) -> None:
    name = model_name(tmp_path / "utils" / "a-b.yml", tmp_path, "pkg.m", "case_1")

    assert name == "_mt_utils_a_b_pkg_m_case_1"


def make_spec(test_dir: Path) -> SpecFile:
    case = Case(name="zero", arguments={"denominator": 0}, expect_rows=[{"result": None}])
    return SpecFile(test_dir / "safe.yml", [MacroSpec("safe_divide", [case])])


def test_build_files_generates_a_model_and_a_unit_test_per_case(tmp_path: Path) -> None:
    files = build_files(RAW, tmp_path, tmp_path, [make_spec(tmp_path)], packages_yml=None)

    assert files["models/_mt_safe_safe_divide_zero.sql"] == (
        "select {{ safe_divide(denominator=0) }} as result\n"
    )
    assert yaml.safe_load(files["models/_unit_tests.yml"]) == {
        "unit_tests": [
            {
                "name": "zero",
                "model": "_mt_safe_safe_divide_zero",
                "given": [],
                "expect": {"rows": [{"result": None}]},
            }
        ]
    }
    assert "packages.yml" not in files


def test_build_files_carries_packages_yml_over(tmp_path: Path) -> None:
    files = build_files(RAW, tmp_path, tmp_path, [], packages_yml="packages: []\n")

    assert files["packages.yml"] == "packages: []\n"


def test_write_project_replaces_the_previous_output(tmp_path: Path) -> None:
    out = tmp_path / "out"
    write_project({"stale.txt": "old"}, out)

    write_project({"models/a.sql": "select 1"}, out)

    assert (out / "models" / "a.sql").read_text() == "select 1"
    assert not (out / "stale.txt").exists()


def test_carried_over_says_what_is_taken_and_what_is_left_out(tmp_path: Path) -> None:
    (tmp_path / "packages.yml").write_text("packages: []\n")

    lines = carried_over(RAW, tmp_path)

    assert "project: shop (profile: shop)" in lines
    assert f"macro directories: {tmp_path / 'macros'}, {tmp_path / 'more'}" in lines
    assert "vars: country" in lines
    assert "dispatch entries: 1" in lines
    assert "packages.yml: copied" in lines
    assert "run hooks left out: on-run-start, on-run-end" in lines


def test_carried_over_for_a_bare_project(tmp_path: Path) -> None:
    lines = carried_over({"name": "x", "profile": "x"}, tmp_path)

    assert "vars: none" in lines
    assert "dispatch entries: 0" in lines
    assert "packages.yml: none" in lines
    assert "run hooks left out: none" in lines
