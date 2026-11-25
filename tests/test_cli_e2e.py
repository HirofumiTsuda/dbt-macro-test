import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner
from dbt.cli.main import dbtRunner

from dbt_macro_test.cli import main

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
    (project / "macro_test" / "us.yml").write_text(
        "macros:\n"
        "  - macro: greeting\n"
        "    cases:\n"
        "      - name: reads_the_environment\n"
        "        given: {arguments: {name: World}}\n"
        "        expect: {rows: [{result: 'Hello, World! country=US'}]}\n"
    )

    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "us.yml")])

    assert result.exit_code == 0, result.output


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
    (project / "macro_test" / "wrong_output.yml").write_text(
        "macros:\n"
        "  - macro: with_alias\n"
        "    cases:\n"
        "      - name: forgot_output_columns\n"
        "        given: {arguments: {x: 1}}\n"
        "        expect: {rows: [{amount: 1}]}\n"
    )

    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "wrong_output.yml")])

    assert result.exit_code == 1
    assert "SQL generated for the case that errored" in result.output
    assert "select {{ with_alias(x=1) }} as result" in result.output


def test_run_reports_a_wrong_argument_name_before_running_dbt(project: Path) -> None:
    (project / "macro_test" / "typo.yml").write_text(
        "macros:\n"
        "  - macro: safe_divide\n"
        "    cases:\n"
        "      - name: typo\n"
        "        given: {arguments: {numeratr: 10, denominator: 4}}\n"
        "        expect: {rows: [{result: 2.5}]}\n"
    )

    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "typo.yml")])

    assert result.exit_code == 1
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
    (project / "macro_test" / "refs.yml").write_text(
        "macros:\n"
        "  - macro: orders_count\n"
        "    cases:\n"
        "      - name: counts_orders\n"
        "        expect: {rows: [{result: 1}]}\n"
    )

    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "refs.yml")])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "Error: dbt test could not run; see dbt's message above" in result.output
    assert "Traceback" not in result.output


def test_run_fails_when_a_case_does_not_match(project: Path) -> None:
    (project / "macro_test" / "wrong.yml").write_text(
        "macros:\n"
        "  - macro: safe_divide\n"
        "    cases:\n"
        "      - name: wrong_on_purpose\n"
        "        given: {arguments: {numerator: 10, denominator: 4}}\n"
        "        expect: {rows: [{result: 9.9}]}\n"
    )

    result = CliRunner().invoke(main, ["run", str(project / "macro_test")])

    assert result.exit_code == 1


def test_run_accepts_a_single_spec_file(project: Path) -> None:
    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "greeting.yml")])

    assert result.exit_code == 0, result.output


def test_run_reports_an_invalid_spec_without_running_dbt(project: Path) -> None:
    bad = project / "macro_test" / "bad.yml"
    bad.write_text("macros: 1\n")

    result = CliRunner().invoke(main, ["run", str(bad)])

    assert result.exit_code == 1
    assert "macros: must be a list" in result.output
    assert not (project / "target" / "macro_test").exists()


def test_run_outside_a_dbt_project_is_an_error(tmp_path: Path) -> None:
    spec = tmp_path / "a.yml"
    spec.write_text("macros:\n  - {macro: x, cases: [{name: a, expect: {rows: []}}]}\n")

    result = CliRunner().invoke(main, ["run", str(spec)])

    assert result.exit_code == 1
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

    assert result.exit_code == 1
    assert "Error: dbt test could not run; see dbt's message above" in result.output
