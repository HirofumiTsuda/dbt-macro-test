import re
import shutil
from pathlib import Path
from typing import Any

import duckdb
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


@pytest.fixture
def small_project(project: Path) -> Path:
    """The fixture project with a single spec left in macro_test/, for the tests that are about
    finding the project and the specs and not about what the cases do."""
    for spec in (project / "macro_test").glob("*.yml"):
        if spec.name != "greeting.yml":
            spec.unlink()
    return project


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
    monkeypatch.setenv("DMT_COUNTRY", "US")
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
    small_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(small_project / "macros")

    result = CliRunner().invoke(main, ["run"])

    assert result.exit_code == 0, result.output


def test_run_uses_the_project_given_even_when_started_elsewhere(
    small_project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    result = CliRunner().invoke(main, ["run", "--project-dir", str(small_project)])

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
    small_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(small_project)

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


def test_a_broken_case_outside_the_selection_does_not_run(small_project: Path) -> None:
    write_wrong_division(small_project)
    specs = str(small_project / "macro_test")

    selected = CliRunner().invoke(main, ["run", "--select", "greeting", specs])
    everything = CliRunner().invoke(main, ["run", specs])

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
    spec = write_wrong_division(project)

    result = CliRunner().invoke(main, ["run", str(spec)])

    assert result.exit_code == 1
    assert "1 failed" in result.output


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


def run_text(project: Path, macro: str, case: str, rows: list[dict[str, str]], **kw: Any) -> Any:
    spec = write_spec(
        project / "macro_test", f"{case}.yml", macro, case, output="text", rows=rows, **kw
    )
    return CliRunner().invoke(main, ["run", str(spec)])


def test_a_macro_that_returns_text_is_compared_as_text(project: Path) -> None:
    result = run_text(
        project, "hello", "greets", [{"result": "Hello, World!"}], arguments={"name": "World"}
    )

    assert result.exit_code == 0, result.output
    assert "1 passed" in result.output


def test_the_same_text_is_an_error_when_it_is_taken_for_an_expression(project: Path) -> None:
    spec = write_spec(
        project / "macro_test",
        "as_expression.yml",
        "hello",
        "greets",
        arguments={"name": "World"},
        rows=[{"result": "Hello, World!"}],
    )

    result = CliRunner().invoke(main, ["run", str(spec)])

    assert result.exit_code == 1
    assert "1 errored" in result.output


def test_a_wrong_text_fails_and_shows_both_texts(project: Path) -> None:
    result = run_text(
        project, "hello", "wrong", [{"result": "Hello, there!"}], arguments={"name": "World"}
    )

    assert result.exit_code == 1
    assert "1 failed" in result.output
    assert "Hello, World!" in result.output
    assert "Hello, there!" in result.output


def test_single_quotes_in_the_text_are_escaped_by_dbt(project: Path) -> None:
    result = run_text(project, "with_quotes", "quoted", [{"result": "it's a 'quoted' word"}])

    assert result.exit_code == 0, result.output


def test_blank_space_at_either_end_of_the_text_is_dropped(project: Path) -> None:
    result = run_text(project, "padded", "trimmed", [{"result": "indented text"}])

    assert result.exit_code == 0, result.output


def test_text_that_keeps_its_inner_line_breaks_can_be_expected_whole(project: Path) -> None:
    statement = "\n".join(
        [
            'merge into "main"."orders" as t',
            'using "main"."orders_new" as s',
            "on t.id = s.id",
            "when matched then update set t.value = s.value",
            "when not matched then insert (id, value) values (s.id, s.value)",
        ]
    )
    relation = "api.Relation.create(schema='main', identifier='{}')"

    result = run_text(
        project,
        "upsert_sql",
        "merges_on_id",
        [{"result": statement}],
        arguments={
            "target": {"type": "jinja", "value": relation.format("orders")},
            "source": {"type": "jinja", "value": relation.format("orders_new")},
            "key": "id",
        },
    )

    assert result.exit_code == 0, result.output


def test_a_changed_statement_is_found_by_the_text(project: Path) -> None:
    relation = "api.Relation.create(schema='main', identifier='{}')"

    result = run_text(
        project,
        "upsert_sql",
        "wrong_key",
        [{"result": 'merge into "main"."orders" as t'}],
        arguments={
            "target": {"type": "jinja", "value": relation.format("orders")},
            "source": {"type": "jinja", "value": relation.format("orders_new")},
            "key": "id",
        },
    )

    assert result.exit_code == 1
    assert "1 failed" in result.output


def plain(text: str) -> str:
    """dbt's output without the colour codes, which split a phrase such as `actual differs`."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def relation(name: str) -> dict[str, str]:
    """The argument that hands a macro the relation that the tool made for the case."""
    return {"type": "jinja", "value": f"relations.{name}"}


TARGET = {"rows": [{"id": 1, "value": "a"}, {"id": 2, "value": "b"}]}
SOURCE = {"sql": "select 2 as id, 'B' as value union all select 3, 'c'"}
MERGED = [{"id": 1, "value": "a"}, {"id": 2, "value": "B"}, {"id": 3, "value": "c"}]


def run_relations(project: Path, name: str, macro: str, **kw: Any) -> Any:
    spec = write_spec(project / "macro_test", f"{name}.yml", macro, name, **kw)
    return CliRunner().invoke(main, ["run", str(spec)])


def test_a_macro_that_runs_a_merge_is_checked_by_the_rows_it_leaves(project: Path) -> None:
    result = run_relations(
        project,
        "merges",
        "upsert_orders",
        setup={"target": TARGET, "source": SOURCE},
        arguments={"target": relation("target"), "source": relation("source")},
        query="select * from {{ relations.target }}",
        rows=MERGED,
    )

    assert result.exit_code == 0, result.output
    assert "1 passed" in result.output


def test_a_wrong_state_fails_and_the_diff_shows_the_rows(project: Path) -> None:
    result = run_relations(
        project,
        "wrong_state",
        "upsert_orders",
        setup={"target": TARGET, "source": SOURCE},
        arguments={"target": relation("target"), "source": relation("source")},
        query="select * from {{ relations.target }}",
        rows=[{"id": 1, "value": "a"}, {"id": 2, "value": "b"}],
    )

    assert result.exit_code == 1
    assert "1 failed" in result.output
    assert "actual differs from expected" in plain(result.output)
    assert "+++,3 ,c" in plain(result.output)


def test_a_statement_of_the_macro_is_run_once_and_not_once_per_render(project: Path) -> None:
    result = run_relations(
        project,
        "appends_once",
        "append_row",
        setup={"target": {"rows": [{"id": 1, "value": "a"}]}},
        arguments={"target": relation("target")},
        query="select * from {{ relations.target }}",
        rows=[{"id": 1, "value": "a"}, {"id": 9, "value": "new"}],
    )

    assert result.exit_code == 0, result.output


def test_a_relation_may_be_made_from_another_that_was_made_before_it(project: Path) -> None:
    result = run_relations(
        project,
        "copies",
        "row_count",
        setup={
            "target": TARGET,
            "copy": {"sql": "select * from {{ relations.target }} where id > 1"},
        },
        arguments={"table": relation("copy")},
        rows=[{"result": 1}],
    )

    assert result.exit_code == 0, result.output


def test_relations_without_a_query_compare_what_the_macro_returns(project: Path) -> None:
    result = run_relations(
        project,
        "counts",
        "row_count",
        setup={"target": TARGET},
        arguments={"table": relation("target")},
        rows=[{"result": 2}],
    )

    assert result.exit_code == 0, result.output


def test_a_string_with_a_quote_and_a_line_break_survives_the_rows_of_a_relation(
    project: Path,
) -> None:
    result = run_relations(
        project,
        "quoted",
        "row_count",
        setup={"target": {"rows": [{"id": 1, "value": 'it\'s\n"x"'}]}},
        arguments={"table": relation("target")},
        query="select value as result from {{ relations.target }}",
        rows=[{"result": 'it\'s\n"x"'}],
    )

    assert result.exit_code == 0, result.output


def test_a_select_of_a_relation_that_fails_errors_the_case_and_shows_the_model(
    project: Path,
) -> None:
    result = run_relations(
        project,
        "bad_select",
        "append_row",
        setup={"target": {"sql": "select from from"}},
        arguments={"target": relation("target")},
        query="select 1 as id",
        rows=[{"id": 1}],
    )

    assert result.exit_code == 1
    assert "1 errored" in result.output
    assert "SQL generated for the case that errored" in result.output
    assert "create_table_as(true" in result.output


def test_a_case_that_gives_both_an_output_and_a_query_is_not_run(project: Path) -> None:
    result = run_relations(
        project,
        "both",
        "append_row",
        arguments={"target": "t"},
        output="columns",
        query="select 1 as id",
        rows=[{"id": 1}],
    )

    assert result.exit_code == 2
    assert "give one or the other" in result.output


def file_database(project: Path, tmp_path: Path) -> Path:
    database = tmp_path / "left_behind.duckdb"
    (project / "profiles.yml").write_text(
        "fixture_project:\n  target: dev\n  outputs:\n    dev:\n      type: duckdb\n"
        f'      path: "{database.as_posix()}"\n'
    )
    return database


def tables_in(database: Path) -> list[str]:
    # dbt keeps its own connection to the file in this process, so this one is opened as it was
    connection = duckdb.connect(str(database))
    found = connection.execute(
        "select table_name from information_schema.tables "
        "where table_schema not in ('information_schema', 'pg_catalog')"
    ).fetchall()
    connection.close()
    return [name for (name,) in found]


def two_cases(project: Path) -> tuple[Any, Any]:
    passing = run_relations(
        project,
        "passes",
        "upsert_orders",
        setup={"target": TARGET, "source": SOURCE},
        arguments={"target": relation("target"), "source": relation("source")},
        query="select * from {{ relations.target }}",
        rows=MERGED,
    )
    failing = run_relations(
        project,
        "fails",
        "upsert_orders",
        setup={"target": TARGET, "source": SOURCE},
        arguments={"target": relation("target"), "source": relation("source")},
        query="select * from {{ relations.target }}",
        rows=[{"id": 1, "value": "nope"}],
    )
    return passing, failing


def test_nothing_is_left_in_the_database_after_a_case_that_passes_or_one_that_fails(
    project: Path, tmp_path: Path
) -> None:
    database = file_database(project, tmp_path)

    passing, failing = two_cases(project)

    assert passing.exit_code == 0, passing.output
    assert failing.exit_code == 1
    assert tables_in(database) == []


PERSISTENT = """{% macro duckdb__create_table_as(temporary, relation, compiled_code, language='sql',
                                      partitioned_by=none, sorted_by=none) -%}
  create table {{ relation.include(database=false, schema=false) }} as ({{ compiled_code }})
{%- endmacro %}
"""


def made_by_the_tool(database: Path) -> list[str]:
    """The relations of the cases (`_dmt_...`), apart from what dbt makes for its own unit tests."""
    return [name for name in tables_in(database) if name.startswith("_dmt_")]


def persistent_project(project: Path, tmp_path: Path) -> Path:
    # stands for an adapter whose "temporary" relation is a normal table (BigQuery keeps it for
    # twelve hours, Trino for ever): the project's own create_table_as ignores `temporary`
    (project / "macros" / "persistent.sql").write_text(PERSISTENT)
    return file_database(project, tmp_path)


def test_relations_that_an_adapter_does_not_make_temporary_are_dropped_after_the_run(
    project: Path, tmp_path: Path
) -> None:
    database = persistent_project(project, tmp_path)

    passing, failing = two_cases(project)

    assert passing.exit_code == 0, passing.output
    assert failing.exit_code == 1
    assert made_by_the_tool(database) == []


def test_the_simulation_of_such_an_adapter_does_leave_relations_when_nothing_drops_them(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dbt_macro_test.engine import runner

    database = persistent_project(project, tmp_path)
    monkeypatch.setattr(runner, "drop_relations", lambda *a, **k: [])

    passing, _ = two_cases(project)

    assert passing.exit_code == 0, passing.output
    assert len(made_by_the_tool(database)) >= 2


def test_the_tool_says_which_relations_it_could_not_drop(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dbt_macro_test.engine import runner

    monkeypatch.setattr(runner, "drop_relations", lambda *a, **k: ["_dmt_x_0_target"])

    result = run_relations(
        project,
        "undropped",
        "row_count",
        setup={"target": TARGET},
        arguments={"table": relation("target")},
        rows=[{"result": 2}],
    )

    assert result.exit_code == 0, result.output
    assert "could not be dropped and may be left in the warehouse: _dmt_x_0_target" in result.output


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


def test_run_passes_for_cases_that_expect_an_error(project: Path) -> None:
    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "errors.yml")])

    assert result.exit_code == 0, result.output
    assert "PASS positive::raises_when_not_guarded" in result.output
    assert "PASS guarded_positive::raises_when_guarded" in result.output
    assert "PASS bad_cast::the_warehouse_cannot_convert" in result.output
    assert "4 passed" in result.output


def test_a_case_that_raises_does_not_stop_the_others(project: Path) -> None:
    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "errors.yml")])

    assert result.exit_code == 0, result.output
    assert "PASS positive::raises_when_not_guarded" in result.output
    assert "PASS _dmt_errors_positive_does_not_raise_for_a_good_value" in result.output
    assert "4 passed" in result.output
    assert "failed" not in result.output


def test_an_error_expected_but_not_raised_fails_and_says_what_happened(project: Path) -> None:
    spec = write_spec(
        project / "macro_test",
        "no_error.yml",
        "positive",
        "expects_an_error_that_does_not_come",
        arguments={"x": 5},
        error="x must not be negative",
    )

    result = CliRunner().invoke(main, ["run", str(spec)])

    assert result.exit_code == 1
    assert "FAIL positive::expects_an_error_that_does_not_come" in result.output
    assert "there was none" in result.output
    assert "1 failed" in result.output


def test_an_error_with_other_text_fails_and_shows_the_text_it_had(project: Path) -> None:
    spec = write_spec(
        project / "macro_test",
        "other_text.yml",
        "positive",
        "expects_other_text",
        arguments={"x": -5},
        error="something else entirely",
    )

    result = CliRunner().invoke(main, ["run", str(spec)])

    assert result.exit_code == 1
    assert "but the error was:" in result.output
    assert "x must not be negative, got -5" in result.output


def test_run_passes_for_a_case_that_gives_the_expected_warning(project: Path) -> None:
    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "warnings.yml")])

    assert result.exit_code == 0, result.output
    assert "PASS careful::warns_and_returns_the_value: the warning contains 'careful: 7'" in (
        result.output
    )
    assert "2 passed" in result.output


def test_a_warning_that_does_not_come_fails_and_says_so(project: Path) -> None:
    spec = write_spec(
        project / "macro_test",
        "no_warning.yml",
        "fine",
        "expects_a_warning_that_does_not_come",
        arguments={"x": 1},
        rows=[{"result": 1}],
        warning="careful",
    )

    result = CliRunner().invoke(main, ["run", str(spec)])

    assert result.exit_code == 1
    assert "FAIL fine::expects_a_warning_that_does_not_come" in result.output
    assert "but there was none" in result.output


def test_a_warning_with_other_text_fails_and_lists_what_was_given(project: Path) -> None:
    spec = write_spec(
        project / "macro_test",
        "other_warning.yml",
        "careful",
        "expects_other_text",
        arguments={"x": 7},
        rows=[{"result": 7}],
        warning="something else entirely",
    )

    result = CliRunner().invoke(main, ["run", str(spec)])

    assert result.exit_code == 1
    assert "but the warnings were: careful: 7" in result.output


def test_a_warning_does_not_excuse_rows_that_are_wrong(project: Path) -> None:
    spec = write_spec(
        project / "macro_test",
        "wrong_rows_right_warning.yml",
        "careful",
        "right_warning_wrong_rows",
        arguments={"x": 7},
        rows=[{"result": 999}],
        warning="careful: 7",
    )

    result = CliRunner().invoke(main, ["run", str(spec)])

    assert result.exit_code == 1
    assert "the case did not pass (fail)" in result.output


def test_a_warning_of_one_case_is_not_taken_for_the_warning_of_another(project: Path) -> None:
    write_spec(
        project / "macro_test",
        "two_warning_cases.yml",
        "careful",
        "warns_about_seven",
        arguments={"x": 7},
        rows=[{"result": 7}],
        warning="careful: 7",
    )
    spec = write_spec(
        project / "macro_test",
        "other_case.yml",
        "careful",
        "expects_the_warning_of_another_value",
        arguments={"x": 1},
        rows=[{"result": 1}],
        warning="careful: 7",
    )

    result = CliRunner().invoke(main, ["run", str(spec)])

    assert result.exit_code == 1
    assert "but the warnings were: careful: 1" in result.output


def test_run_fails_when_a_case_does_not_match(project: Path) -> None:
    spec = write_wrong_division(project)

    result = CliRunner().invoke(main, ["run", str(spec)])

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


def write_ref_macros(project: Path) -> None:
    (project / "macros" / "refs.sql").write_text(
        "{% macro orders_count() %}(select count(*) from {{ ref('orders') }}){% endmacro %}\n"
        "{% macro paid_total() %}(select sum(amount) from {{ source('shop', 'payments') }}"
        " where status = 'paid'){% endmacro %}\n"
    )


def test_a_macro_that_calls_ref_and_source_is_given_their_rows(project: Path) -> None:
    write_ref_macros(project)
    spec = project / "macro_test" / "refs.yml"
    spec.write_text(
        """macros:
  - macro: orders_count
    cases:
      - name: counts_the_given_rows
        given:
          inputs:
            - {input: "ref('orders')", rows: [{id: 10}, {id: 20}, {id: 30}]}
        expect: {rows: [{result: 3}]}
  - macro: paid_total
    cases:
      - name: adds_up_the_paid_payments
        given:
          inputs:
            - input: source('shop', 'payments')
              rows:
                - {amount: 100, status: paid}
                - {amount: 50, status: refunded}
                - {amount: 25, status: paid}
        expect: {rows: [{result: 125}]}
"""
    )

    result = CliRunner().invoke(main, ["run", str(spec)])

    assert result.exit_code == 0, result.output
    assert "2 passed" in result.output


def test_a_wrong_expectation_on_the_rows_of_a_ref_fails(project: Path) -> None:
    write_ref_macros(project)
    spec = project / "macro_test" / "refs.yml"
    spec.write_text(
        """macros:
  - macro: orders_count
    cases:
      - name: counts_the_given_rows
        given:
          inputs:
            - {input: "ref('orders')", rows: [{id: 10}, {id: 20}]}
        expect: {rows: [{result: 3}]}
"""
    )

    result = CliRunner().invoke(main, ["run", str(spec)])

    assert result.exit_code == 1
    assert "1 failed" in result.output


def test_a_ref_that_no_case_gives_is_said_to_belong_under_given_inputs(project: Path) -> None:
    write_ref_macros(project)
    write_spec(
        project / "macro_test", "refs.yml", "orders_count", "nothing_given", rows=[{"result": 0}]
    )

    result = CliRunner().invoke(main, ["run", str(project / "macro_test" / "refs.yml")])

    assert result.exit_code == 2
    assert "'orders'" in result.output
    assert "given.inputs" in result.output


def write_merge_text_macro(project: Path) -> None:
    (project / "macros" / "merge_text.sql").write_text(
        "{% macro merge_text(target, source) %}\n"
        "  {{ return(dbt.get_merge_sql(target, source, 'id', "
        "adapter.get_columns_in_relation(target))) }}\n"
        "{% endmacro %}\n"
    )


MERGE_CASE = """macros:
  - macro: merge_text
    cases:
      - name: merges
{run}        setup:
          relations:
            target: {{rows: [{{id: 1, v: old}}, {{id: 2, v: old}}]}}
            source: {{rows: [{{id: 2, v: new}}, {{id: 3, v: new}}]}}
        given:
          arguments:
            target: {{type: jinja, value: relations.target}}
            source: {{type: jinja, value: relations.source}}
        expect:
          query: select id, v from {{{{ relations.target }}}} order by id
          rows: [{{id: 1, v: old}}, {{id: 2, v: new}}, {{id: 3, v: new}}]
"""


def test_a_macro_that_returns_a_statement_is_run_when_the_case_says_execute(project: Path) -> None:
    write_merge_text_macro(project)
    spec = project / "macro_test" / "merge_text.yml"
    spec.write_text(MERGE_CASE.format(run="        run: execute\n"))

    result = CliRunner().invoke(main, ["run", str(spec)])

    assert result.exit_code == 0, result.output
    assert "1 passed" in result.output


def test_the_same_case_without_execute_runs_nothing_and_fails(project: Path) -> None:
    write_merge_text_macro(project)
    spec = project / "macro_test" / "merge_text.yml"
    spec.write_text(MERGE_CASE.format(run=""))

    result = CliRunner().invoke(main, ["run", str(spec)])

    assert result.exit_code == 1
    assert "1 failed" in result.output
