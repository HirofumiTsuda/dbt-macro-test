from pathlib import Path

import pytest

from dbt_macro_test.spec import (
    FixtureRef,
    InlineRows,
    JinjaExpression,
    Output,
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
        ("{}", "needs exactly one of 'rows' and 'fixture'"),
        ("{rows: [], fixture: x}", "needs exactly one of 'rows' and 'fixture'"),
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
            "needs exactly one of 'rows' and 'fixture'",
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
