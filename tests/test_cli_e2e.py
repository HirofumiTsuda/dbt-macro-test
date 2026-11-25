import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from dbt_macro_test.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "project"

pytestmark = pytest.mark.e2e


@pytest.fixture
def project(tmp_path: Path) -> Path:
    destination = tmp_path / "project"
    shutil.copytree(FIXTURE, destination)
    return destination


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
