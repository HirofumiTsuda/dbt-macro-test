from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from dbt_macro_test.project import (
    build_files,
    carried_over,
    macro_call,
    model_name,
    project_config,
    write_project,
)
from dbt_macro_test.project.generate import CLEANUP_PATH, cleanup_macro, new_run_id
from dbt_macro_test.spec import Case, InlineRows, MacroSpec, Overrides, SetupRelation, SpecFile

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

    assert name == "_dmt_utils_a_b_pkg_m_case_1"


def make_spec(test_dir: Path) -> SpecFile:
    case = Case(
        name="zero", arguments={"denominator": 0}, expect=InlineRows("dict", [{"result": None}])
    )
    return SpecFile(test_dir / "safe.yml", [MacroSpec("safe_divide", [case])])


def test_build_files_generates_a_model_and_a_unit_test_per_case(tmp_path: Path) -> None:
    files = build_files(RAW, tmp_path, tmp_path, [make_spec(tmp_path)], packages_yml=None)

    assert files["models/_dmt_safe_safe_divide_zero.sql"] == (
        "select {{ safe_divide(denominator=0) }} as result\n"
    )
    assert yaml.safe_load(files["models/_unit_tests.yml"]) == {
        "unit_tests": [
            {
                "name": "zero",
                "model": "_dmt_safe_safe_divide_zero",
                "given": [],
                "expect": {"format": "dict", "rows": [{"result": None}]},
            }
        ]
    }
    assert "packages.yml" not in files


def test_build_files_emits_overrides_into_the_unit_test_unchanged(tmp_path: Path) -> None:
    overrides = Overrides(macros={"is_running_in_ci": True}, vars={"region": "us"})
    case = Case(name="c", arguments={}, expect=InlineRows("dict", []), overrides=overrides)
    spec = SpecFile(tmp_path / "s.yml", [MacroSpec("m", [case])])

    files = build_files(RAW, tmp_path, tmp_path, [spec])

    unit_test = yaml.safe_load(files["models/_unit_tests.yml"])["unit_tests"][0]
    assert unit_test["overrides"] == overrides


def test_build_files_leaves_out_overrides_when_there_are_none(tmp_path: Path) -> None:
    files = build_files(RAW, tmp_path, tmp_path, [make_spec(tmp_path)])

    assert "overrides" not in yaml.safe_load(files["models/_unit_tests.yml"])["unit_tests"][0]


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
    assert "packages: packages.yml copied (dbt deps is run)" in lines
    assert "run hooks left out: on-run-start, on-run-end" in lines


def test_carried_over_for_a_bare_project(tmp_path: Path) -> None:
    lines = carried_over({"name": "x", "profile": "x"}, tmp_path)

    assert "vars: none" in lines
    assert "dispatch entries: 0" in lines
    assert "packages: none" in lines
    assert "run hooks left out: none" in lines


def test_carried_over_says_when_installed_packages_are_reused(tmp_path: Path) -> None:
    (tmp_path / "packages.yml").write_text("packages: []\n")
    installed = tmp_path / "dbt_packages"

    lines = carried_over(RAW, tmp_path, installed)

    assert f"packages: reusing {installed} (dbt deps is not run)" in lines


def test_project_config_points_at_installed_packages_when_reusing_them(tmp_path: Path) -> None:
    installed = tmp_path / "somewhere" / "dbt_packages"

    config = project_config(RAW, tmp_path, installed)

    assert config["packages-install-path"] == str(installed)


def test_project_config_drops_the_install_path_when_installing_afresh(tmp_path: Path) -> None:
    raw = {**RAW, "packages-install-path": "../vendored"}

    assert "packages-install-path" not in project_config(raw, tmp_path)


def test_build_files_makes_local_package_paths_absolute(tmp_path: Path) -> None:
    files = build_files(RAW, tmp_path, tmp_path, [], packages_yml="packages:\n  - local: ../x\n")

    assert yaml.safe_load(files["packages.yml"])["packages"] == [
        {"local": str((tmp_path / "../x").resolve())}
    ]


def sql_case(**kw: Any) -> Case:
    return Case(name="a", arguments={}, expect=InlineRows("dict", []), **kw)


def test_a_case_without_sql_of_its_own_is_wrapped_by_its_output() -> None:
    assert sql_case().model_sql("m(a=1)") == "select {{ m(a=1) }} as result\n"


def test_a_case_with_relations_and_a_query_makes_them_runs_the_macro_and_ends_with_the_query() -> (
    None
):
    case = sql_case(
        setup=(
            SetupRelation("target", rows=({"id": 1},)),
            SetupRelation("src", sql="select 2 as id"),
        ),
        query="select * from {{ relations.target }}",
    )

    lines = case.model_sql("m(a=1)", "_dmt_r_0_").splitlines()

    assert lines[0] == "{% set relations = namespace() %}"
    assert lines[1] == (
        "{% set relations.target = make_temp_relation(api.Relation.create("
        "database=target.get('database'), schema=target.schema, "
        'identifier="_dmt_r_0_target")) %}'
    )
    assert lines[2].startswith("{% set relations.src = make_temp_relation(")
    assert lines[3] == "{% if execute %}"
    assert lines[4:7] == [
        "{% set _dmt_sql %}select 1 as id{% endset %}",
        "{% do run_query(create_table_as(true, relations.target, _dmt_sql)) %}",
        '{% do log("__dmt_relation__" ~ tojson({"database": relations.target.database, '
        '"schema": relations.target.schema, "identifier": relations.target.identifier, '
        '"type": "table"}), info=false) %}',
    ]
    assert lines[7] == "{% set _dmt_sql %}select 2 as id{% endset %}"
    assert lines[-3:] == [
        "{% do m(a=1) %}",
        "{% endif %}",
        "select * from {{ relations.target }}",
    ]


def test_a_relation_that_is_not_temporary_is_made_with_false_and_without_make_temp_relation() -> (
    None
):
    case = sql_case(
        setup=(
            SetupRelation("kept", rows=({"id": 1},), temporary=False),
            SetupRelation("scratch", sql="select 2 as id"),
        ),
        query="select * from {{ relations.kept }}",
    )

    lines = case.model_sql("m()", "_dmt_r_0_").splitlines()

    # not make_temp_relation: that of Postgres drops the schema and the database of the relation
    assert lines[1] == (
        "{% set relations.kept = api.Relation.create("
        "database=target.get('database'), schema=target.schema, "
        'identifier="_dmt_r_0_kept") %}'
    )
    assert lines[2].startswith("{% set relations.scratch = make_temp_relation(")
    assert "{% do run_query(create_table_as(false, relations.kept, _dmt_sql)) %}" in lines
    assert "{% do run_query(create_table_as(true, relations.scratch, _dmt_sql)) %}" in lines
    # it is still logged, so that the tool drops it
    assert any(
        line.startswith('{% do log("__dmt_relation__"') and "relations.kept" in line
        for line in lines
    )


def test_a_relation_named_like_a_method_of_a_dict_is_still_the_relation() -> None:
    sql = sql_case(setup=(SetupRelation("copy", sql="select 1"),), query="select 1").model_sql(
        "m()"
    )

    assert "{% set relations.copy = make_temp_relation(" in sql
    assert "relations.copy" in sql and "relations.update" not in sql


def test_relations_without_a_query_keep_the_output_of_the_macro_as_the_result() -> None:
    case = sql_case(setup=(SetupRelation("t", sql="select 1 as id"),))

    lines = case.model_sql("m()", "_dmt_r_0_").splitlines()

    assert lines[-2:] == ["{% endif %}", "select {{ m() }} as result"]
    assert "{% do m() %}" not in lines


def test_a_query_without_relations_still_runs_the_macro_first_and_only_at_run_time() -> None:
    assert sql_case(query="select 1 as r").model_sql("m()") == (
        "{% if execute %}\n{% do m() %}\n{% endif %}\nselect 1 as r\n"
    )


def test_the_relations_are_made_only_when_the_model_is_run_not_when_it_is_parsed() -> None:
    sql = sql_case(setup=(SetupRelation("t", sql="select 1"),), query="select 1").model_sql("m()")

    before_execute = sql.split("{% if execute %}")[0]

    assert "run_query" not in before_execute
    assert "make_temp_relation" in before_execute


def test_a_project_with_relations_gets_the_macro_that_drops_them_and_names_by_the_run() -> None:
    case = sql_case(setup=(SetupRelation("t", sql="select 1"),), query="select * from t")
    spec = SpecFile(Path("/p/m/s.yml"), [MacroSpec("m", [case])])

    files = build_files(RAW, Path("/p"), Path("/p/m"), [spec], run_id="20261126T000000_abc123")

    macro = files["macros/_dmt_drop.sql"].split("#}", 1)[1]  # the macro, not its comment
    assert "drop_relation(relation)" in macro
    assert "auto_begin=True" in macro  # a transaction, for the commit to have something to commit
    assert "adapter.commit()" in macro
    assert yaml.safe_load(files["dbt_project.yml"])["macro-paths"][-1] == "macros"
    model = next(v for k, v in files.items() if k.startswith("models/_dmt_") and k.endswith(".sql"))
    assert '"_dmt_20261126T000000_abc123_0_t"' in model


def test_the_macro_that_drops_the_relations_is_a_file_of_the_package() -> None:
    packaged = resources.files("dbt_macro_test.project").joinpath("macros/_dmt_drop.sql")

    text = packaged.read_text()

    assert cleanup_macro() == text
    assert "{% macro _dmt_drop(relations) %}" in text
    assert CLEANUP_PATH == "macros/_dmt_drop.sql"


def test_the_part_of_a_relation_name_that_the_tool_chooses_leaves_room_for_the_name() -> None:
    # An adapter adds a suffix to it (Postgres, whose names stop at 63 characters, adds 21 and
    # cuts the end of what it is given, so what the tool puts first is kept): the more this takes,
    # the less is left of the author's name. A project of up to 999 cases stays within 32.
    assert len(f"_dmt_{new_run_id()}_999_") <= 32


def test_a_project_without_relations_is_as_before() -> None:
    spec = SpecFile(Path("/p/m/s.yml"), [MacroSpec("m", [sql_case()])])

    files = build_files(RAW, Path("/p"), Path("/p/m"), [spec])

    assert "macros/_dmt_drop.sql" not in files
    assert "macros" not in yaml.safe_load(files["dbt_project.yml"])["macro-paths"]


def test_each_case_of_a_project_has_names_of_its_own() -> None:
    cases = [
        Case(
            name=name,
            arguments={},
            expect=InlineRows("dict", []),
            setup=(SetupRelation("t", sql="select 1"),),
            query="select 1",
        )
        for name in ("first", "second")
    ]
    spec = SpecFile(Path("/p/m/s.yml"), [MacroSpec("m", cases)])

    files = build_files(RAW, Path("/p"), Path("/p/m"), [spec], run_id="r")

    first = next(v for k, v in files.items() if k.endswith("first.sql"))
    second = next(v for k, v in files.items() if k.endswith("second.sql"))
    assert '"_dmt_r_0_t"' in first and '"_dmt_r_1_t"' not in first
    assert '"_dmt_r_1_t"' in second and '"_dmt_r_0_t"' not in second


def test_inputs_become_stand_in_nodes_and_the_given_of_the_unit_test_in_sql() -> None:
    from dbt_macro_test.spec import GivenInput

    case = Case(
        name="a",
        arguments={},
        expect=InlineRows("dict", [{"result": 1}]),
        inputs=(
            GivenInput("ref", ("orders",), rows=({"id": 1},)),
            GivenInput("source", ("shop", "payments"), sql="select 2 as order_id"),
        ),
    )
    other = Case(
        name="b",
        arguments={},
        expect=InlineRows("dict", [{"result": 1}]),
        inputs=(GivenInput("ref", ("orders",), rows=({"id": 9},)),),
    )
    spec = SpecFile(Path("/p/m/s.yml"), [MacroSpec("m", [case, other])])

    files = build_files(RAW, Path("/p"), Path("/p/m"), [spec], run_id="r")

    assert files["models/orders.sql"] == "select 1 as stand_in\n"  # once, for both cases
    assert yaml.safe_load(files["models/_sources.yml"]) == {
        "sources": [{"name": "shop", "tables": [{"name": "payments"}]}]
    }
    given_a, given_b = (
        t["given"] for t in yaml.safe_load(files["models/_unit_tests.yml"])["unit_tests"]
    )
    assert given_a == [
        {"input": "ref('orders')", "format": "sql", "rows": "select 1 as id"},
        {"input": "source('shop', 'payments')", "format": "sql", "rows": "select 2 as order_id"},
    ]
    assert given_b[0]["rows"] == "select 9 as id"


def test_a_project_without_inputs_has_no_stand_in_nodes() -> None:
    spec = SpecFile(Path("/p/m/s.yml"), [MacroSpec("m", [sql_case(query="select 1")])])

    files = build_files(RAW, Path("/p"), Path("/p/m"), [spec], run_id="r")

    assert "models/_sources.yml" not in files
    assert [k for k in files if k.startswith("models/") and "_dmt_" not in k] == [
        "models/_unit_tests.yml"
    ]


def test_a_case_that_executes_runs_the_statement_the_macro_returns_instead_of_dropping_it() -> None:
    called = sql_case(setup=(SetupRelation("t", sql="select 1"),), query="select 1")
    executed = sql_case(setup=(SetupRelation("t", sql="select 1"),), query="select 1", execute=True)

    assert "{% do m(a=1) %}" in called.model_sql("m(a=1)").splitlines()
    assert "{% do run_query(m(a=1)) %}" in executed.model_sql("m(a=1)").splitlines()
