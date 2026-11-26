from pathlib import Path

import pytest

from dbt_macro_test.spec import (
    ExpectedError,
    ExpectedWarning,
    FixtureRef,
    InlineRows,
    JinjaExpression,
    Output,
    Overrides,
    SpecError,
    find_spec_files,
    load_spec_file,
    load_specs,
)


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "spec.yml"
    path.write_text(text)
    return path


VALID = """
macros:
  - macro: safe_divide
    cases:
      - name: by_zero
        given:
          arguments: {numerator: 10, denominator: 0}
        expect:
          rows:
            - {result: null}
      - name: no_arguments
        expect:
          rows: []
"""


def test_valid_spec_is_loaded(tmp_path: Path) -> None:
    spec = load_spec_file(write(tmp_path, VALID))

    assert [m.macro for m in spec.macros] == ["safe_divide"]
    by_zero, no_arguments = spec.macros[0].cases
    assert by_zero.name == "by_zero"
    assert by_zero.arguments == {"numerator": 10, "denominator": 0}
    assert by_zero.expect == InlineRows("dict", [{"result": None}])
    assert no_arguments.arguments == {}
    assert no_arguments.expect == InlineRows("dict", [])


def case_with(expect: str) -> str:
    return f"macros:\n  - macro: m\n    cases:\n      - {{name: a, expect: {expect}}}\n"


def test_expect_defaults_to_rows_as_mappings(tmp_path: Path) -> None:
    (case,) = load_spec_file(write(tmp_path, case_with("{rows: [{r: 1}]}"))).macros[0].cases

    assert case.expect == InlineRows("dict", [{"r": 1}])


def test_expect_can_be_csv_or_sql_text(tmp_path: Path) -> None:
    csv_case, sql_case = [
        load_spec_file(write(tmp_path, case_with(e))).macros[0].cases[0]
        for e in ('{format: csv, rows: "a,b\\n1,2"}', "{format: sql, rows: 'select 1 as a'}")
    ]

    assert csv_case.expect == InlineRows("csv", "a,b\n1,2")
    assert sql_case.expect == InlineRows("sql", "select 1 as a")


def test_expect_can_name_a_fixture(tmp_path: Path) -> None:
    (case,) = load_spec_file(write(tmp_path, case_with("{fixture: numbers}"))).macros[0].cases

    assert case.expect == FixtureRef("numbers")


@pytest.mark.parametrize(
    ("expect", "message"),
    [
        ("{}", "needs exactly one of 'rows', 'fixture' and 'error'"),
        ("{rows: [], fixture: x}", "needs exactly one of 'rows', 'fixture' and 'error'"),
        ("{format: csv, fixture: x}", "a fixture says its format by its extension"),
        ("{fixture: 'a b'}", "'a b' is not a fixture name"),
        ("{fixture: 1}", "1 is not a fixture name"),
        ("{format: json, rows: x}", "'json' is not one of: dict, csv, sql"),
        ("{format: csv, rows: [{a: 1}]}", "must be text, with format csv"),
        ("{format: sql, rows: ''}", "must be text, with format sql"),
        ("{format: dict, rows: 'a,b'}", "expect.rows: must be a list"),
        ("{rows: [1]}", "expect.rows[0]: must be a mapping"),
    ],
)
def test_invalid_expectations_are_reported(tmp_path: Path, expect: str, message: str) -> None:
    with pytest.raises(SpecError) as error:
        load_spec_file(write(tmp_path, case_with(expect)))

    assert message in str(error.value)


def test_expect_can_be_an_error_with_a_message(tmp_path: Path) -> None:
    text = case_with("{error: {message: must not be negative}}")

    (case,) = load_spec_file(write(tmp_path, text)).macros[0].cases

    assert case.expect == ExpectedError("must not be negative")
    assert case.expect.isolated is True


def test_only_a_case_that_expects_an_error_runs_alone(tmp_path: Path) -> None:
    rows = load_spec_file(write(tmp_path, case_with("{rows: []}"))).macros[0].cases[0]
    fixture = load_spec_file(write(tmp_path, case_with("{fixture: numbers}"))).macros[0].cases[0]

    assert (rows.expect.isolated, fixture.expect.isolated) == (False, False)


@pytest.mark.parametrize(
    ("expect", "message"),
    [
        ("{error: {}}", "missing required key 'message'"),
        ("{error: {message: ''}}", "must be the text the error contains"),
        ("{error: {message: 1}}", "must be the text the error contains"),
        ("{error: {message: x, extra: 1}}", "unknown key(s): extra"),
        ("{error: boom}", "expect.error: must be a mapping"),
        ("{error: {message: x}, rows: []}", "needs exactly one of 'rows', 'fixture' and 'error'"),
        ("{error: {message: x}, fixture: n}", "needs exactly one of 'rows', 'fixture' and 'error'"),
        ("{error: {message: x}, format: csv}", "'format' goes with 'rows', not with 'error'"),
    ],
)
def test_invalid_error_expectations_are_reported(tmp_path: Path, expect: str, message: str) -> None:
    with pytest.raises(SpecError) as error:
        load_spec_file(write(tmp_path, case_with(expect)))

    assert message in str(error.value)


def test_expect_can_add_a_warning_to_rows(tmp_path: Path) -> None:
    text = case_with("{rows: [{r: 1}], warning: {message: careful}}")

    (case,) = load_spec_file(write(tmp_path, text)).macros[0].cases

    assert case.expect == InlineRows("dict", [{"r": 1}])
    assert case.warning == ExpectedWarning("careful")
    assert case.isolated is True


def test_expect_can_add_a_warning_to_a_fixture(tmp_path: Path) -> None:
    text = case_with("{fixture: numbers, warning: {message: careful}}")

    (case,) = load_spec_file(write(tmp_path, text)).macros[0].cases

    assert case.expect == FixtureRef("numbers")
    assert case.warning == ExpectedWarning("careful")


def test_a_case_without_a_warning_runs_with_the_others_unless_it_expects_an_error(
    tmp_path: Path,
) -> None:
    rows = load_spec_file(write(tmp_path, case_with("{rows: []}"))).macros[0].cases[0]
    error = load_spec_file(write(tmp_path, case_with("{error: {message: x}}"))).macros[0].cases[0]

    assert (rows.warning, rows.isolated) == (None, False)
    assert (error.warning, error.isolated) == (None, True)


@pytest.mark.parametrize(
    ("expect", "message"),
    [
        ("{warning: {message: x}}", "needs exactly one of 'rows', 'fixture' and 'error'"),
        ("{rows: [], warning: {}}", "missing required key 'message'"),
        ("{rows: [], warning: {message: ''}}", "must be the text the warning contains"),
        ("{rows: [], warning: {message: 1}}", "must be the text the warning contains"),
        ("{rows: [], warning: {message: x, extra: 1}}", "unknown key(s): extra"),
        ("{rows: [], warning: careful}", "expect.warning: must be a mapping"),
        (
            "{error: {message: x}, warning: {message: y}}",
            "a case that ends in an error cannot also expect a warning",
        ),
    ],
)
def test_invalid_warning_expectations_are_reported(
    tmp_path: Path, expect: str, message: str
) -> None:
    with pytest.raises(SpecError) as error:
        load_spec_file(write(tmp_path, case_with(expect)))

    assert message in str(error.value)


def setup_case(extra: str = "", expect: str = "{rows: [{r: 1}], query: select 1 as r}") -> str:
    return f"macros:\n  - macro: m\n    cases:\n      - name: a\n        expect: {expect}\n{extra}"


def test_a_case_can_make_relations_and_give_a_query_to_compare(tmp_path: Path) -> None:
    text = setup_case(
        "        setup:\n          relations:\n"
        "            target: {rows: [{id: 1, v: a}]}\n"
        "            source: {sql: 'select 2 as id'}\n"
    )

    (case,) = load_spec_file(write(tmp_path, text)).macros[0].cases

    assert [r.name for r in case.setup] == ["target", "source"]
    assert case.setup[0].rows == ({"id": 1, "v": "a"},)
    assert case.setup[1].sql == "select 2 as id"
    assert case.query == "select 1 as r"
    assert case.runs_own_sql is True


def test_a_case_without_sql_of_its_own_is_as_before(tmp_path: Path) -> None:
    (case,) = load_spec_file(write(tmp_path, case_with("{rows: [{r: 1}]}"))).macros[0].cases

    assert (case.setup, case.query, case.runs_own_sql) == ((), None, False)


def test_relations_without_a_query_make_a_case_that_runs_its_own_sql(tmp_path: Path) -> None:
    text = setup_case("        setup: {relations: {t: {sql: select 1}}}\n", "{rows: [{r: 1}]}")

    (case,) = load_spec_file(write(tmp_path, text)).macros[0].cases

    assert (case.query, case.runs_own_sql) == (None, True)


@pytest.mark.parametrize(
    ("extra", "expect", "message"),
    [
        ("        setup: [t]\n", "{rows: []}", "setup: must be a mapping"),
        ("        setup: {}\n", "{rows: []}", "missing required key 'relations'"),
        ("        setup: {relations: {}}\n", "{rows: []}", "must have at least one relation"),
        (
            "        setup: {relations: {t: {}}}\n",
            "{rows: []}",
            "needs exactly one of 'rows' and 'sql'",
        ),
        (
            "        setup: {relations: {t: {rows: [{a: 1}], sql: select 1}}}\n",
            "{rows: []}",
            "needs exactly one of 'rows' and 'sql'",
        ),
        ("        setup: {relations: {t: {sql: ''}}}\n", "{rows: []}", "must be a select, as text"),
        (
            "        setup: {relations: {t: {rows: []}}}\n",
            "{rows: []}",
            "must have at least one row",
        ),
        ("        setup: {relations: {t: {rows: [1]}}}\n", "{rows: []}", "must be a mapping"),
        (
            "        setup: {relations: {t: {rows: [{a: 1}, {b: 2}]}}}\n",
            "{rows: []}",
            "row 1 has the columns",
        ),
        (
            "        setup: {relations: {t: {rows: [{a: [1]}]}}}\n",
            "{rows: []}",
            "use `sql` for it",
        ),
        (
            "        setup: {relations: {'a b': {sql: select 1}}}\n",
            "{rows: []}",
            "is not a relation name",
        ),
        (
            "        setup: {relations: {t: {sql: select 1}}, sql: [x]}\n",
            "{rows: []}",
            "unknown key(s): sql",
        ),
        ("", "{rows: [], query: ''}", "must be the SQL of a query"),
        ("", "{rows: [], query: 3}", "must be the SQL of a query"),
        ("", "{error: {message: x}, query: select 1}", "no query to compare"),
        ("        output: query\n", "{rows: [], query: select 1}", "give one or the other"),
    ],
)
def test_invalid_setup_and_query_are_reported(
    tmp_path: Path, extra: str, expect: str, message: str
) -> None:
    with pytest.raises(SpecError) as error:
        load_spec_file(write(tmp_path, setup_case(extra, expect)))

    assert message in str(error.value)


def test_output_can_be_query(tmp_path: Path) -> None:
    text = (
        "macros:\n  - macro: x\n    cases:\n      - {name: a, output: query, expect: {rows: []}}\n"
    )

    (case,) = load_spec_file(write(tmp_path, text)).macros[0].cases

    assert case.output is Output.QUERY


def test_output_defaults_to_expression_and_can_be_columns(tmp_path: Path) -> None:
    text = (
        "macros:\n"
        "  - macro: x\n"
        "    cases:\n"
        "      - {name: a, expect: {rows: []}}\n"
        "      - {name: b, output: columns, expect: {rows: []}}\n"
    )

    a, b = load_spec_file(write(tmp_path, text)).macros[0].cases

    assert (a.output, b.output) == (Output.EXPRESSION, Output.COLUMNS)


def test_arguments_can_be_plain_values_or_typed(tmp_path: Path) -> None:
    text = (
        "macros:\n"
        "  - macro: m\n"
        "    cases:\n"
        "      - name: a\n"
        "        given:\n"
        "          arguments:\n"
        "            plain: 1\n"
        "            a_dict: {k: v}\n"
        "            as_literal: {type: literal, value: {type: jinja}}\n"
        "            bare: {type: jinja, value: \"api.Relation.create(schema='s')\"}\n"
        "            wrapped: {type: jinja, value: \"{{ ref('x') }}\"}\n"
        "        expect: {rows: []}\n"
    )

    arguments = load_spec_file(write(tmp_path, text)).macros[0].cases[0].arguments

    assert arguments["plain"] == 1
    assert arguments["a_dict"] == {"k": "v"}
    assert arguments["as_literal"] == {"type": "jinja"}
    assert arguments["bare"] == JinjaExpression("api.Relation.create(schema='s')")
    assert arguments["wrapped"] == JinjaExpression("ref('x')")


@pytest.mark.parametrize(
    ("argument", "message"),
    [
        ("{type: jinja}", "missing required key 'value'"),
        ("{type: jinja, value: 1}", "must be a string holding a Jinja expression"),
        ("{type: jinja, value: '{{ }}'}", "is an empty Jinja expression"),
        ("{type: jinja, value: x, extra: 1}", "unknown key(s): extra"),
    ],
)
def test_a_malformed_typed_argument_is_reported(
    tmp_path: Path, argument: str, message: str
) -> None:
    text = (
        "macros:\n  - macro: m\n    cases:\n"
        f"      - {{name: a, given: {{arguments: {{x: {argument}}}}}, expect: {{rows: []}}}}\n"
    )

    with pytest.raises(SpecError) as error:
        load_spec_file(write(tmp_path, text))

    assert message in str(error.value)


def test_overrides_default_to_none_and_keep_only_what_is_given(tmp_path: Path) -> None:
    text = (
        "macros:\n"
        "  - macro: m\n"
        "    cases:\n"
        "      - {name: a, expect: {rows: []}}\n"
        "      - name: b\n"
        "        overrides: {vars: {region: us}, macros: {is_running_in_ci: true}}\n"
        "        expect: {rows: []}\n"
    )

    a, b = load_spec_file(write(tmp_path, text)).macros[0].cases

    assert a.overrides == {}
    assert b.overrides == {"vars": {"region": "us"}, "macros": {"is_running_in_ci": True}}


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            "{target: {schema: s}}",
            "cannot override target; dbt's unit tests accept: macros, vars, env_vars",
        ),
        ("{vars: {a: 1}, nope: 1, target: 2}", "cannot override nope, target"),
        ("[vars]", "overrides: must be a mapping"),
        ("{vars: 1}", "overrides.vars: must be a mapping"),
        ("{env_vars: [A]}", "overrides.env_vars: must be a mapping"),
    ],
)
def test_invalid_overrides_are_reported(tmp_path: Path, overrides: str, message: str) -> None:
    text = (
        "macros:\n  - macro: m\n    cases:\n"
        f"      - {{name: a, overrides: {overrides}, expect: {{rows: []}}}}\n"
    )

    with pytest.raises(SpecError) as error:
        load_spec_file(write(tmp_path, text))

    assert message in str(error.value)


def test_the_kinds_of_override_come_from_the_typed_dict_and_are_the_three_dbt_has() -> None:
    assert tuple(Overrides.__annotations__) == ("macros", "vars", "env_vars")


def test_package_qualified_macro_name_is_accepted(tmp_path: Path) -> None:
    text = "macros:\n  - macro: dbt_utils.star\n    cases:\n      - {name: a, expect: {rows: []}}\n"

    assert load_spec_file(write(tmp_path, text)).macros[0].macro == "dbt_utils.star"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "top level: must be a mapping"),
        ("macros: 1", "macros: must be a list"),
        ("{}", "missing required key 'macros'"),
        (
            "macros:\n  - {macro: x, cases: [{name: a, output: nope, expect: {rows: []}}]}",
            "'nope' is not one of: expression, columns, query",
        ),
        ("other: 1", "unknown key(s): other"),
        ("macros:\n  - macro: x", "missing required key 'cases'"),
        ("macros:\n  - {macro: 'a b', cases: []}", "'a b' is not a macro name"),
        ("macros:\n  - {macro: x, cases: []}", "must have at least one case"),
        (
            "macros:\n  - {macro: x, cases: [{name: a, expect: {rows: []}, extra: 1}]}",
            "unknown key(s): extra",
        ),
        (
            "macros:\n  - {macro: x, cases: [{name: 'a b', expect: {rows: []}}]}",
            "'a b' is not a valid name",
        ),
        (
            "macros:\n  - {macro: x, cases: [{name: a, expect: {rows: []}},"
            " {name: a, expect: {rows: []}}]}",
            "duplicate case name(s): a",
        ),
        (
            "macros:\n  - {macro: x, cases: [{name: a, given: {arguments: [1]},"
            " expect: {rows: []}}]}",
            "given.arguments: must be a mapping",
        ),
        (
            "macros:\n  - {macro: x, cases: [{name: a, expect: {}}]}",
            "needs exactly one of 'rows', 'fixture' and 'error'",
        ),
        (
            "macros:\n  - {macro: x, cases: [{name: a, expect: {rows: [1]}}]}",
            "expect.rows[0]: must be a mapping",
        ),
    ],
)
def test_invalid_spec_is_reported_with_its_location(
    tmp_path: Path, text: str, message: str
) -> None:
    path = write(tmp_path, text)

    with pytest.raises(SpecError, match="spec.yml") as error:
        load_spec_file(path)

    assert message in str(error.value)


def test_invalid_yaml_is_reported(tmp_path: Path) -> None:
    with pytest.raises(SpecError, match="invalid YAML"):
        load_spec_file(write(tmp_path, "macros: [unclosed"))


def test_directory_is_searched_recursively(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.yml").write_text(VALID)
    (tmp_path / "sub" / "b.yaml").write_text(VALID)

    assert [p.name for p in find_spec_files(tmp_path)] == ["a.yml", "b.yaml"]
    assert len(load_specs(tmp_path)) == 2


def test_directory_without_specs_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(SpecError, match="no spec files"):
        find_spec_files(tmp_path)


def inputs_case(inputs: str) -> str:
    return (
        "macros:\n  - macro: m\n    cases:\n      - name: a\n        expect: {rows: [{r: 1}]}\n"
        f"        given:\n          inputs:\n{inputs}"
    )


def test_a_case_can_give_the_rows_of_a_ref_and_of_a_source(tmp_path: Path) -> None:
    text = inputs_case(
        "            - {input: \"ref('orders')\", rows: [{id: 1}]}\n"
        "            - {input: \"source('shop', 'payments')\", sql: 'select 2 as id'}\n"
    )

    (case,) = load_spec_file(write(tmp_path, text)).macros[0].cases

    assert [i.reference for i in case.inputs] == ["ref('orders')", "source('shop', 'payments')"]
    assert case.inputs[0].rows == ({"id": 1},)
    assert case.inputs[1].sql == "select 2 as id"
    assert case.arguments == {}


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        ("            - {rows: [{id: 1}]}\n", "'input'"),
        ("            - {input: orders, rows: [{id: 1}]}\n", "is not ref('model')"),
        ("            - {input: \"ref('p', 'orders')\", rows: [{id: 1}]}\n", "not supported"),
        ("            - {input: \"source('orders')\", rows: [{id: 1}]}\n", "its table"),
        ("            - {input: \"ref('o')\"}\n", "exactly one of 'rows' and 'sql'"),
        ("            - {input: \"ref('o')\", rows: []}\n", "at least one row"),
        ('            - {input: "ref(\'o\')", rows: [{s: "it\'s"}]}\n', "use `sql` for it"),
        (
            "            - {input: \"ref('o')\", rows: [{id: 1}]}\n"
            "            - {input: \"ref('o')\", rows: [{id: 2}]}\n",
            "is given twice",
        ),
    ],
)
def test_invalid_inputs_are_reported(tmp_path: Path, inputs: str, message: str) -> None:
    with pytest.raises(SpecError) as error:
        load_spec_file(write(tmp_path, inputs_case(inputs)))

    assert message in str(error.value)


def run_case(extra: str, expect: str = "{rows: [{r: 1}], query: select 1 as r}") -> str:
    return f"macros:\n  - macro: m\n    cases:\n      - name: a\n{extra}        expect: {expect}\n"


def test_run_is_call_unless_it_says_execute(tmp_path: Path) -> None:
    (plain,) = load_spec_file(write(tmp_path, run_case(""))).macros[0].cases
    (called,) = load_spec_file(write(tmp_path, run_case("        run: call\n"))).macros[0].cases
    (executed,) = (
        load_spec_file(write(tmp_path, run_case("        run: execute\n"))).macros[0].cases
    )

    assert [plain.execute, called.execute, executed.execute] == [False, False, True]


@pytest.mark.parametrize(
    ("extra", "expect", "message"),
    [
        (
            "        run: now\n",
            "{rows: [{r: 1}], query: select 1 as r}",
            "is not 'call' or 'execute'",
        ),
        ("        run: execute\n", "{rows: [{r: 1}]}", "so give one"),
    ],
)
def test_invalid_run_is_reported(tmp_path: Path, extra: str, expect: str, message: str) -> None:
    with pytest.raises(SpecError) as error:
        load_spec_file(write(tmp_path, run_case(extra, expect)))

    assert message in str(error.value)
