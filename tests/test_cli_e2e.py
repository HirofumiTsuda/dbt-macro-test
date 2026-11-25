import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner
from dbt.cli.main import dbtRunner

from dbt_macro_test.cli import main
from tests.spec_writer import write_spec

FIXTURE = Path(__file__).parent / "fixtures" / "project"

pytestmark = pytest.mark.e2e


@pytest.fixture
def project(tmp_path: Path) -> Path:
    destination = tmp_path / "project"
    shutil.copytree(FIXTURE, destination)
    return destination


def test_run_adds_nothing_to_the_project_but_the_file_dbt_itself_writes(project: Path) -> None:
    dbt_user_id_file = ".user.yml"
    before = {p.name for p in project.iterdir()}

    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "greeting.yml")])

    assert result.exit_code == 0, result.output
    assert {p.name for p in project.iterdir()} - before - {dbt_user_id_file} == set()


def test_run_keeps_the_generated_project_when_asked(project: Path) -> None:
    result = CliRunner().invoke(
        main, ["run", "--keep-generated", str(project / "macro_test" / "greeting.yml")]
    )

    assert result.exit_code == 0, result.output
    kept = Path(result.output.split("Generated project kept at ")[1].strip())
    try:
        assert (kept / "dbt_project.yml").is_file()
        assert kept.parent != project
    finally:
        shutil.rmtree(kept, ignore_errors=True)


def test_run_says_what_it_carries_over_when_verbose(project: Path) -> None:
    result = CliRunner().invoke(
        main, ["run", "--verbose", str(project / "macro_test" / "greeting.yml")]
    )

    assert result.exit_code == 0, result.output
    assert "Carried over from the project:" in result.output
    assert "project: fixture_project (profile: fixture_project)" in result.output
    assert "vars: country" in result.output
    assert "run hooks left out: on-run-start" in result.output


def test_run_takes_a_var_from_the_environment(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MT_COUNTRY", "US")
    write_spec(
        project / "macro_test",
        "us.yml",
        "greeting",
        "reads_the_environment",
        arguments={"name": "World"},
        rows=[{"result": "Hello, World! country=US"}],
    )

    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "us.yml")])

    assert result.exit_code == 0, result.output


def test_run_finds_the_project_from_a_subdirectory(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(project / "macros")

    result = CliRunner().invoke(main, ["run"])

    assert result.exit_code == 0, result.output


def test_run_uses_the_project_given_even_when_started_elsewhere(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    result = CliRunner().invoke(main, ["run", "--project-dir", str(project)])

    assert result.exit_code == 0, result.output


def test_run_says_when_the_default_specs_directory_is_missing(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shutil.rmtree(project / "macro_test")
    monkeypatch.chdir(project)

    result = CliRunner().invoke(main, ["run"])

    assert result.exit_code == 2
    assert "macro_test does not exist; put the specs there or give their path" in result.output


def test_run_says_when_the_given_project_has_no_project_file(tmp_path: Path) -> None:
    result = CliRunner().invoke(main, ["run", "--project-dir", str(tmp_path)])

    assert result.exit_code == 2
    assert "no dbt_project.yml in" in result.output


def test_the_environment_variable_beats_the_projects_own_profiles_file(
    project: Path, tmp_path: Path
) -> None:
    empty = tmp_path / "empty_profiles"
    empty.mkdir()
    (empty / "profiles.yml").write_text("some_other_profile: {}\n")

    result = CliRunner().invoke(
        main,
        ["run", "--verbose", str(project / "macro_test" / "greeting.yml")],
        env={"DBT_PROFILES_DIR": str(empty)},
    )

    assert result.exit_code == 2
    assert "profiles.yml from: DBT_PROFILES_DIR" in result.output
    assert "Error: dbt test could not run" in result.output


def test_the_profiles_flag_beats_the_environment_variable(project: Path, tmp_path: Path) -> None:
    empty = tmp_path / "empty_profiles"
    empty.mkdir()
    (empty / "profiles.yml").write_text("some_other_profile: {}\n")

    result = CliRunner().invoke(
        main,
        [
            "run",
            "--verbose",
            "--profiles-dir",
            str(project),
            str(project / "macro_test" / "greeting.yml"),
        ],
        env={"DBT_PROFILES_DIR": str(empty)},
    )

    assert result.exit_code == 0, result.output
    assert "profiles.yml from: --profiles-dir" in result.output


def write_wrong_division(project: Path) -> Path:
    """A case that does not hold: 10 / 4 is not 9.9."""
    return write_spec(
        project / "macro_test",
        "wrong.yml",
        "safe_divide",
        "wrong_on_purpose",
        arguments={"numerator": 10, "denominator": 4},
        rows=[{"result": 9.9}],
    )


def test_run_passes_when_every_case_matches(project: Path) -> None:
    result = CliRunner().invoke(main, ["run", str(project / "macro_test")])

    assert result.exit_code == 0, result.output


def test_run_without_arguments_uses_macro_test_in_the_current_directory(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(project)

    result = CliRunner().invoke(main, ["run"])

    assert result.exit_code == 0, result.output


def test_run_passes_for_macros_that_return_columns(project: Path) -> None:
    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "columns.yml")])

    assert result.exit_code == 0, result.output


def test_run_shows_the_generated_sql_when_a_case_errors(project: Path) -> None:
    write_spec(
        project / "macro_test",
        "wrong_output.yml",
        "with_alias",
        "forgot_output_columns",
        arguments={"x": 1},
        rows=[{"amount": 1}],
    )

    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "wrong_output.yml")])

    assert result.exit_code == 1
    assert "SQL generated for the case that errored" in result.output
    assert "select {{ with_alias(x=1) }} as result" in result.output


def test_run_reports_a_wrong_argument_name_before_running_dbt(project: Path) -> None:
    write_spec(
        project / "macro_test",
        "typo.yml",
        "safe_divide",
        "typo",
        arguments={"numeratr": 10, "denominator": 4},
        rows=[{"result": 2.5}],
    )

    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "typo.yml")])

    assert result.exit_code == 2
    assert "unknown argument 'numeratr'" in result.output
    assert "the macro takes: numerator, denominator" in result.output
    assert "missing argument 'numerator'" in result.output
    assert not (project / "target" / "macro_test").exists()


def test_run_passes_defaults_and_jinja_expression_arguments(project: Path) -> None:
    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "arguments.yml")])

    assert result.exit_code == 0, result.output


def test_run_shows_a_failure_of_dbt_as_an_error_not_a_traceback(project: Path) -> None:
    (project / "macros" / "refs.sql").write_text(
        "{% macro orders_count() %}(select count(*) from {{ ref('orders') }}){% endmacro %}\n"
    )
    write_spec(
        project / "macro_test", "refs.yml", "orders_count", "counts_orders", rows=[{"result": 1}]
    )

    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "refs.yml")])

    assert result.exit_code == 2
    assert isinstance(result.exception, SystemExit)
    assert "Error: dbt test could not run; see dbt's message above" in result.output
    assert "Traceback" not in result.output


def test_select_runs_only_the_matching_cases(project: Path) -> None:
    result = CliRunner().invoke(
        main,
        ["run", "--select", "safe_divide::plain_division", str(project / "macro_test")],
    )

    assert result.exit_code == 0, result.output
    assert "Selected 1 of " in result.output
    assert "\n1 passed" in result.output


def test_select_by_macro_name_and_wildcard(project: Path) -> None:
    result = CliRunner().invoke(
        main, ["run", "--select", "safe_*", "--select", "shout", str(project / "macro_test")]
    )

    assert result.exit_code == 0, result.output
    assert "Selected 3 of " in result.output
    assert "\n3 passed" in result.output


def test_select_that_matches_nothing_could_not_run_and_lists_the_cases(project: Path) -> None:
    result = CliRunner().invoke(main, ["run", "--select", "nope", str(project / "macro_test")])

    assert result.exit_code == 2
    assert "no case matches nope" in result.output
    assert "safe_divide::plain_division" in result.output


def test_a_broken_case_outside_the_selection_does_not_run(project: Path) -> None:
    write_wrong_division(project)

    selected = CliRunner().invoke(
        main, ["run", "--select", "greeting", str(project / "macro_test")]
    )
    everything = CliRunner().invoke(main, ["run", str(project / "macro_test")])

    assert selected.exit_code == 0, selected.output
    assert everything.exit_code == 1


def test_list_prints_the_cases_without_running_dbt(project: Path) -> None:
    result = CliRunner().invoke(
        main, ["run", "--list", "--select", "shout", str(project / "macro_test")]
    )

    assert result.exit_code == 0, result.output
    assert "shout::from_the_second_macro_path" in result.output
    assert "Running with dbt" not in result.output


def test_a_failing_case_exits_1_and_the_summary_counts_it(project: Path) -> None:
    write_wrong_division(project)

    result = CliRunner().invoke(main, ["run", str(project / "macro_test")])

    assert result.exit_code == 1
    assert "1 failed, " in result.output


def test_run_applies_macro_var_and_env_var_overrides(project: Path) -> None:
    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "overrides.yml")])

    assert result.exit_code == 0, result.output
    assert "4 passed" in result.output


def test_a_wrong_override_expectation_fails(project: Path) -> None:
    write_spec(
        project / "macro_test",
        "wrong_override.yml",
        "schema_for",
        "override_not_expected",
        arguments={"name": "x"},
        overrides={"macros": {"is_running_in_ci": True}},
        rows=[{"result": "x|eu|dev"}],
    )

    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "wrong_override.yml")])

    assert result.exit_code == 1


def test_run_rejects_an_override_dbt_does_not_have(project: Path) -> None:
    write_spec(
        project / "macro_test",
        "target.yml",
        "schema_for",
        "with_target",
        arguments={"name": "x"},
        overrides={"target": {"schema": "s"}},
        rows=[],
    )

    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "target.yml")])

    assert result.exit_code == 2
    assert (
        "cannot override target; dbt's unit tests accept: macros, vars, env_vars" in result.output
    )


def write_greet_case_overriding(project: Path, macro_key: str) -> Path:
    return write_spec(
        project / "macro_test",
        "package_override.yml",
        "greet",
        "overrides_a_package_macro",
        overrides={"macros": {macro_key: "overridden"}},
        rows=[{"result": "overridden"}],
    )


def test_a_package_macro_is_overridden_under_its_qualified_name(
    project_with_packages: Path,
) -> None:
    spec = write_greet_case_overriding(project_with_packages, "spike_utils.hello")

    result = CliRunner().invoke(main, ["run", str(spec)])

    assert result.exit_code == 0, result.output


def test_a_package_macro_is_not_overridden_under_its_bare_name(
    project_with_packages: Path,
) -> None:
    spec = write_greet_case_overriding(project_with_packages, "hello")

    result = CliRunner().invoke(main, ["run", str(spec)])

    assert result.exit_code == 1
    assert "1 failed" in result.output


def test_run_passes_for_macros_that_return_a_whole_query(project: Path) -> None:
    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "queries.yml")])

    assert result.exit_code == 0, result.output
    assert "3 passed" in result.output


def test_a_query_with_a_wrong_row_fails(project: Path) -> None:
    write_spec(
        project / "macro_test",
        "wrong_rows.yml",
        "union_two",
        "one_row_missing",
        arguments={"a": "(select 1 as id)", "b": "(select 2 as id)"},
        output="query",
        rows=[{"id": 1}],
    )

    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "wrong_rows.yml")])

    assert result.exit_code == 1
    assert "1 failed" in result.output


def test_run_passes_for_every_way_of_writing_the_expected_rows(project: Path) -> None:
    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "formats.yml")])

    assert result.exit_code == 0, result.output
    assert "5 passed" in result.output


def test_a_wrong_composite_value_fails_and_the_diff_shows_the_values(project: Path) -> None:
    spec = write_spec(
        project / "macro_test",
        "wrong_composite.yml",
        "composite_columns",
        "wrong_list_and_map",
        output="columns",
        expect_format="sql",
        rows="select [1, 2, 4] as l, {'a': 1, 'b': 'x'} as s, map {'k1': 1, 'k2': 9} as m",
    )

    result = CliRunner().invoke(main, ["run", str(spec)])

    assert result.exit_code == 1
    assert "1 failed" in result.output


def test_a_fixture_that_is_not_there_could_not_run_and_says_where_it_looked(
    project: Path,
) -> None:
    spec = write_spec(
        project / "macro_test",
        "missing.yml",
        "numbers",
        "needs_a_fixture",
        output="query",
        fixture="not_there",
    )

    result = CliRunner().invoke(main, ["run", str(spec)])

    assert result.exit_code == 2
    assert "no fixture 'not_there'" in result.output
    assert str(project / "macro_test" / "fixtures") in result.output


def test_run_fails_when_a_case_does_not_match(project: Path) -> None:
    write_wrong_division(project)

    result = CliRunner().invoke(main, ["run", str(project / "macro_test")])

    assert result.exit_code == 1


def test_run_accepts_a_single_spec_file(project: Path) -> None:
    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "greeting.yml")])

    assert result.exit_code == 0, result.output


def test_run_reports_an_invalid_spec_without_running_dbt(project: Path) -> None:
    bad = project / "macro_test" / "bad.yml"
    bad.write_text("macros: 1\n")

    result = CliRunner().invoke(main, ["run", str(bad)])

    assert result.exit_code == 2
    assert "macros: must be a list" in result.output
    assert not (project / "target" / "macro_test").exists()


def test_run_outside_a_dbt_project_is_an_error(tmp_path: Path) -> None:
    spec = tmp_path / "a.yml"
    spec.write_text("macros:\n  - {macro: x, cases: [{name: a, expect: {rows: []}}]}\n")

    result = CliRunner().invoke(main, ["run", str(spec)])

    assert result.exit_code == 2
    assert "no dbt_project.yml" in result.output


def test_the_run_hooks_of_the_project_do_not_run(project: Path) -> None:
    (project / "dbt_project.yml").write_text(
        (project / "dbt_project.yml").read_text().replace('"select 1"', '"select * from missing"')
    )

    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "greeting.yml")])

    assert result.exit_code == 0, result.output


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def project_with_packages(tmp_path: Path) -> Path:
    shutil.copytree(FIXTURES / "packages", tmp_path / "packages")
    destination = tmp_path / "project"
    shutil.copytree(FIXTURES / "project_with_packages", destination)
    return destination


def install_packages(project: Path) -> None:
    result = dbtRunner().invoke(
        ["deps", "--project-dir", str(project), "--profiles-dir", str(project)]
    )
    assert result.success, result.exception


def test_run_installs_packages_and_keeps_the_projects_dispatch(project_with_packages: Path) -> None:
    result = CliRunner().invoke(
        main, ["run", "--verbose", str(project_with_packages / "macro_test")]
    )

    assert result.exit_code == 0, result.output
    assert "packages: packages.yml copied (dbt deps is run)" in result.output
    assert not (project_with_packages / "dbt_packages").exists()


def test_run_reuses_installed_packages_without_touching_them(
    project_with_packages: Path,
) -> None:
    install_packages(project_with_packages)
    installed = project_with_packages / "dbt_packages"
    before = sorted(p.name for p in installed.iterdir())
    modified = {p: p.stat().st_mtime_ns for p in installed.rglob("*") if p.is_file()}

    result = CliRunner().invoke(
        main,
        ["run", "--verbose", "--keep-generated", str(project_with_packages / "macro_test")],
    )

    assert result.exit_code == 0, result.output
    assert f"packages: reusing {installed.resolve()} (dbt deps is not run)" in result.output
    kept = Path(result.output.split("Generated project kept at ")[1].strip())
    try:
        assert not (kept / "dbt_packages").exists()
    finally:
        shutil.rmtree(kept, ignore_errors=True)
    assert sorted(p.name for p in installed.iterdir()) == before
    assert {p: p.stat().st_mtime_ns for p in installed.rglob("*") if p.is_file()} == modified


def test_run_stops_when_the_installed_packages_do_not_match_packages_yml(
    project_with_packages: Path,
) -> None:
    install_packages(project_with_packages)
    packages_yml = project_with_packages / "packages.yml"
    packages_yml.write_text(packages_yml.read_text() + "  - local: ../packages/other_utils\n")

    result = CliRunner().invoke(main, ["run", str(project_with_packages / "macro_test")])

    assert result.exit_code == 2
    assert "Error: dbt test could not run; see dbt's message above" in result.output
