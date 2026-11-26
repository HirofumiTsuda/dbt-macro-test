import re
from collections.abc import Collection
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict

import yaml

from dbt_macro_test.spec.expectation import (
    Expectation,
    ExpectedError,
    ExpectedWarning,
    FixtureRef,
    InlineRows,
)
from dbt_macro_test.spec.inputs import GivenInput, parse_reference
from dbt_macro_test.spec.literals import JinjaExpression, to_jinja_literal
from dbt_macro_test.spec.output import Output
from dbt_macro_test.spec.setup import RELATION_MARK, SetupRelation, rows_to_select

_TYPES = ("literal", "jinja")
_FORMATS = ("dict", "csv", "sql")
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MACRO_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")


class Overrides(TypedDict, total=False):
    """What dbt's own unit tests accept under `overrides`; what is not given is left out."""

    macros: dict[str, Any]
    vars: dict[str, Any]
    env_vars: dict[str, Any]


_OVERRIDE_KINDS = tuple(Overrides.__annotations__)


class SpecError(Exception):
    """A spec file is not valid."""


@dataclass(frozen=True)
class Case:
    name: str
    arguments: dict[str, Any]
    expect: Expectation
    output: Output = Output.EXPRESSION
    overrides: Overrides = field(default_factory=lambda: Overrides())
    warning: ExpectedWarning | None = None
    setup: tuple[SetupRelation, ...] = ()
    query: str | None = None
    inputs: tuple[GivenInput, ...] = ()

    @property
    def runs_own_sql(self) -> bool:
        """Whether the case brings SQL of its own: relations to make, and a query that says what
        to compare. Such a case runs against the warehouse more than a unit test does."""
        return bool(self.setup) or self.query is not None

    def model_sql(self, call: str, relation_prefix: str = "") -> str:
        """The throwaway model of the case: what dbt compares with the expected rows.

        A case without SQL of its own wraps the call by its `output`. A case with a `setup` makes
        its relations first, as **temporary** ones, with dbt's own `make_temp_relation` and
        `create_table_as`, which each adapter implements for itself, so nothing here is adapter
        specific. They are made when dbt renders the model at run time (`run_query`), in the
        connection dbt gives the test, and their names are logged so that the tool can drop them
        afterwards (`__dmt_relation__`): a temporary relation is not temporary on every adapter.
        With a `query` the macro is then run for what it does, its text dropped, and the model is
        the query; without one, the macro's output is the model, as before.
        """
        if not self.runs_own_sql:
            return self.output.model_sql(call)
        lines: list[str] = []
        if self.setup:
            # a namespace and not a dict: `relations.copy` of a dict is its method, not the relation
            lines.append("{% set relations = namespace() %}")
            for relation in self.setup:
                identifier = to_jinja_literal(f"{relation_prefix}{relation.name}")
                lines.append(
                    f"{{% set relations.{relation.name} = make_temp_relation("
                    f"api.Relation.create(database=target.get('database'), "
                    f"schema=target.schema, identifier={identifier})) %}}"
                )
        lines.append("{% if execute %}")
        for relation in self.setup:
            ref = f"relations.{relation.name}"
            lines.append(f"{{% set _dmt_sql %}}{relation.select_sql()}{{% endset %}}")
            lines.append(f"{{% do run_query(create_table_as(true, {ref}, _dmt_sql)) %}}")
            lines.append(
                f'{{% do log("{RELATION_MARK}" ~ tojson({{'
                f'"database": {ref}.database, "schema": {ref}.schema, '
                f'"identifier": {ref}.identifier, "type": "table"}}), info=false) %}}'
            )
        if self.query is not None:
            lines.append(f"{{% do {call} %}}")
        lines.append("{% endif %}")
        if self.query is None:
            lines.append(self.output.model_sql(call).rstrip("\n"))
        else:
            lines.append(self.query.strip())
        return "\n".join(lines) + "\n"

    @property
    def isolated(self) -> bool:
        """Whether the case runs on its own: it expects an error, or a warning that has to be
        told apart from the warnings of the other cases."""
        return self.expect.isolated or self.warning is not None


@dataclass(frozen=True)
class MacroSpec:
    macro: str
    cases: list[Case]


@dataclass(frozen=True)
class SpecFile:
    path: Path
    macros: list[MacroSpec]


def find_spec_files(path: Path) -> list[Path]:
    """The spec files at `path`: the file itself, or every YAML file under a directory."""
    if path.is_file():
        return [path]
    files = sorted([*path.rglob("*.yml"), *path.rglob("*.yaml")])
    if not files:
        raise SpecError(f"{path}: no spec files (*.yml, *.yaml) found")
    return files


def load_specs(path: Path) -> list[SpecFile]:
    return [load_spec_file(p) for p in find_spec_files(path)]


def load_spec_file(path: Path) -> SpecFile:
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise SpecError(f"{path}: invalid YAML: {e}") from e
    return _parse_file(data, path)


def _fail(path: Path, where: str, message: str) -> SpecError:
    return SpecError(f"{path}: {where}: {message}")


def _mapping(
    value: Any,
    path: Path,
    where: str,
    *,
    required: Collection[str] = (),
    optional: Collection[str] = (),
    any_keys: bool = False,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _fail(path, where, "must be a mapping")
    unknown = sorted(str(k) for k in value if k not in required and k not in optional)
    if unknown and not any_keys:
        raise _fail(path, where, f"unknown key(s): {', '.join(unknown)}")
    for key in required:
        if key not in value:
            raise _fail(path, where, f"missing required key {key!r}")
    return value


def _list(value: Any, path: Path, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise _fail(path, where, "must be a list")
    return value


def _parse_file(data: Any, path: Path) -> SpecFile:
    top = _mapping(data, path, "top level", required=["macros"])
    entries = _list(top["macros"], path, "macros")
    return SpecFile(
        path=path,
        macros=[_parse_macro(entry, path, f"macros[{i}]") for i, entry in enumerate(entries)],
    )


def _parse_macro(entry: Any, path: Path, where: str) -> MacroSpec:
    body = _mapping(entry, path, where, required=["macro", "cases"])
    macro = body["macro"]
    if not isinstance(macro, str) or not _MACRO_NAME.match(macro):
        raise _fail(path, f"{where}.macro", f"{macro!r} is not a macro name")
    raw_cases = _list(body["cases"], path, f"{where}.cases")
    if not raw_cases:
        raise _fail(path, f"{where}.cases", "must have at least one case")
    cases = [_parse_case(c, path, f"{where}.cases[{i}]") for i, c in enumerate(raw_cases)]
    names = [c.name for c in cases]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise _fail(path, f"{where}.cases", f"duplicate case name(s): {', '.join(duplicates)}")
    return MacroSpec(macro=macro, cases=cases)


def _parse_argument(value: Any, path: Path, where: str) -> Any:
    """A plain value is passed as it is; {type: jinja, value: ...} is an expression."""
    if not isinstance(value, dict) or value.get("type") not in _TYPES:
        return value
    typed = _mapping(value, path, where, required=["type", "value"])
    if typed["type"] == "literal":
        return typed["value"]
    expression = typed["value"]
    if not isinstance(expression, str):
        raise _fail(path, f"{where}.value", "must be a string holding a Jinja expression")
    expression = expression.strip()
    if expression.startswith("{{") and expression.endswith("}}"):
        expression = expression[2:-2].strip()
    if not expression:
        raise _fail(path, f"{where}.value", "is an empty Jinja expression")
    return JinjaExpression(expression)


def _parse_overrides(value: Any, path: Path, where: str) -> Overrides:
    """What dbt's own unit tests accept under `overrides`: macros, vars and env_vars."""
    if isinstance(value, dict):
        unknown = sorted(str(k) for k in value if k not in _OVERRIDE_KINDS)
        if unknown:
            raise _fail(
                path,
                where,
                f"cannot override {', '.join(unknown)}; "
                f"dbt's unit tests accept: {', '.join(_OVERRIDE_KINDS)}",
            )
    given = _mapping(value, path, where, optional=_OVERRIDE_KINDS)
    overrides = Overrides()
    if "macros" in given:
        overrides["macros"] = dict(
            _mapping(given["macros"], path, f"{where}.macros", any_keys=True)
        )
    if "vars" in given:
        overrides["vars"] = dict(_mapping(given["vars"], path, f"{where}.vars", any_keys=True))
    if "env_vars" in given:
        overrides["env_vars"] = dict(
            _mapping(given["env_vars"], path, f"{where}.env_vars", any_keys=True)
        )
    return overrides


def _parse_name(value: Any, path: Path, where: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.match(value):
        raise _fail(path, f"{where}.name", f"{value!r} is not a valid name (letters, digits, _)")
    return value


def _parse_output(value: Any, path: Path, where: str) -> Output:
    try:
        return Output.parse(value)
    except ValueError as e:
        raise _fail(path, f"{where}.output", str(e)) from e


def _parse_given(
    value: Any, path: Path, where: str
) -> tuple[dict[str, Any], tuple[GivenInput, ...]]:
    """The arguments and the inputs of the case; `given` may also be left out, or have neither."""
    given = _mapping(value, path, f"{where}.given", optional=["arguments", "inputs"])
    inputs = _parse_inputs(given["inputs"], path, where) if "inputs" in given else ()
    if "arguments" not in given:
        return {}, inputs
    arguments = _mapping(given["arguments"], path, f"{where}.given.arguments", any_keys=True)
    for key in arguments:
        if not isinstance(key, str) or not _IDENTIFIER.match(key):
            raise _fail(path, f"{where}.given.arguments", f"{key!r} is not an argument name")
    return {
        key: _parse_argument(argument, path, f"{where}.given.arguments.{key}")
        for key, argument in arguments.items()
    }, inputs


def _parse_inputs(value: Any, path: Path, where: str) -> tuple[GivenInput, ...]:
    """`inputs: [{input: ref('orders'), rows: [...]} | {input: ..., sql: select ...}]`."""
    here = f"{where}.given.inputs"
    entries = _list(value, path, here)
    inputs: list[GivenInput] = []
    for i, entry in enumerate(entries):
        spot = f"{here}[{i}]"
        body = _mapping(entry, path, spot, required=["input"], optional=["rows", "sql"])
        reference = body["input"]
        try:
            if not isinstance(reference, str):
                raise ValueError("must be ref('model') or source('source', 'table')")
            kind, names = parse_reference(reference)
        except ValueError as e:
            raise _fail(path, f"{spot}.input", str(e)) from e
        if sum(key in body for key in ("rows", "sql")) != 1:
            raise _fail(path, spot, "needs exactly one of 'rows' and 'sql'")
        if "sql" in body:
            sql = body["sql"]
            if not isinstance(sql, str) or not sql.strip():
                raise _fail(path, f"{spot}.sql", "must be a select, as text")
            given = GivenInput(kind, names, sql=sql)
        else:
            rows = _list(body["rows"], path, f"{spot}.rows")
            if not rows:
                raise _fail(path, f"{spot}.rows", "must have at least one row (use `sql` for none)")
            for j, row in enumerate(rows):
                _mapping(row, path, f"{spot}.rows[{j}]", any_keys=True)
            given = GivenInput(kind, names, rows=tuple(rows))
            try:
                given.select_sql()
            except (ValueError, TypeError) as e:
                raise _fail(path, f"{spot}.rows", str(e)) from e
        if any(other.reference == given.reference for other in inputs):
            raise _fail(path, f"{spot}.input", f"{given.reference} is given twice")
        inputs.append(given)
    return tuple(inputs)


def _parse_expect(value: Any, path: Path, where: str) -> Expectation:
    """What a case expects: rows written in it, rows in a fixture file, or an error; one of them."""
    here = f"{where}.expect"
    expect = _mapping(
        value, path, here, optional=["rows", "format", "fixture", "error", "warning", "query"]
    )
    if sum(key in expect for key in ("rows", "fixture", "error")) != 1:
        raise _fail(path, here, "needs exactly one of 'rows', 'fixture' and 'error'")
    if "error" in expect:
        return _parse_error(expect, path, here)
    if "fixture" in expect:
        return _parse_fixture(expect, path, here)
    return _parse_inline_rows(expect, path, here)


def _parse_warning(value: Any, path: Path, where: str) -> ExpectedWarning | None:
    """The warning a case expects with its rows, if it expects one."""
    here = f"{where}.expect"
    expect = _mapping(
        value, path, here, optional=["rows", "format", "fixture", "error", "warning", "query"]
    )
    if "warning" not in expect:
        return None
    if "error" in expect:
        raise _fail(path, here, "a case that ends in an error cannot also expect a warning")
    warning = _mapping(expect["warning"], path, f"{here}.warning", required=["message"])
    message = warning["message"]
    if not isinstance(message, str) or not message.strip():
        raise _fail(path, f"{here}.warning.message", "must be the text the warning contains")
    return ExpectedWarning(message)


def _parse_query(value: Any, path: Path, where: str) -> str | None:
    """The query a case compares after the macro has run, if it has one."""
    here = f"{where}.expect"
    expect = _mapping(
        value, path, here, optional=["rows", "format", "fixture", "error", "warning", "query"]
    )
    if "query" not in expect:
        return None
    if "error" in expect:
        raise _fail(path, here, "a case that ends in an error has no query to compare")
    query = expect["query"]
    if not isinstance(query, str) or not query.strip():
        raise _fail(path, f"{here}.query", "must be the SQL of a query")
    return query


def _parse_setup(value: Any, path: Path, where: str) -> tuple[SetupRelation, ...]:
    """The relations a case needs: `setup: {relations: {name: {rows: [...]} | {sql: ...}}}`."""
    here = f"{where}.setup"
    setup = _mapping(value, path, here, required=["relations"])
    entries = _mapping(setup["relations"], path, f"{here}.relations", any_keys=True)
    if not entries:
        raise _fail(path, f"{here}.relations", "must have at least one relation")
    relations = []
    for name, entry in entries.items():
        if not isinstance(name, str) or not _IDENTIFIER.match(name):
            raise _fail(path, f"{here}.relations", f"{name!r} is not a relation name")
        spot = f"{here}.relations.{name}"
        body = _mapping(entry, path, spot, optional=["rows", "sql"])
        if sum(key in body for key in ("rows", "sql")) != 1:
            raise _fail(path, spot, "needs exactly one of 'rows' and 'sql'")
        if "sql" in body:
            sql = body["sql"]
            if not isinstance(sql, str) or not sql.strip():
                raise _fail(path, f"{spot}.sql", "must be a select, as text")
            relations.append(SetupRelation(name, sql=sql))
            continue
        rows = _list(body["rows"], path, f"{spot}.rows")
        if not rows:
            raise _fail(path, f"{spot}.rows", "must have at least one row (use `sql` for none)")
        for i, row in enumerate(rows):
            _mapping(row, path, f"{spot}.rows[{i}]", any_keys=True)
        try:
            rows_to_select(rows)
        except (ValueError, TypeError) as e:
            raise _fail(path, f"{spot}.rows", str(e)) from e
        relations.append(SetupRelation(name, rows=tuple(rows)))
    return tuple(relations)


def _parse_error(expect: dict[str, Any], path: Path, here: str) -> ExpectedError:
    if "format" in expect:
        raise _fail(path, here, "'format' goes with 'rows', not with 'error'")
    error = _mapping(expect["error"], path, f"{here}.error", required=["message"])
    message = error["message"]
    if not isinstance(message, str) or not message.strip():
        raise _fail(path, f"{here}.error.message", "must be the text the error contains")
    return ExpectedError(message)


def _parse_fixture(expect: dict[str, Any], path: Path, here: str) -> FixtureRef:
    if "format" in expect:
        raise _fail(path, here, "a fixture says its format by its extension (.csv or .sql)")
    name = expect["fixture"]
    if not isinstance(name, str) or not _IDENTIFIER.match(name):
        raise _fail(path, f"{here}.fixture", f"{name!r} is not a fixture name")
    return FixtureRef(name)


def _parse_inline_rows(expect: dict[str, Any], path: Path, here: str) -> InlineRows:
    format_ = expect.get("format", "dict")
    if format_ not in _FORMATS:
        raise _fail(path, f"{here}.format", f"{format_!r} is not one of: {', '.join(_FORMATS)}")
    if format_ == "dict":
        rows = _list(expect["rows"], path, f"{here}.rows")
        for i, row in enumerate(rows):
            _mapping(row, path, f"{here}.rows[{i}]", any_keys=True)
        return InlineRows("dict", rows)
    text = expect["rows"]
    if not isinstance(text, str) or not text.strip():
        raise _fail(path, f"{here}.rows", f"must be text, with format {format_}")
    return InlineRows(format_, text)


def _parse_case(entry: Any, path: Path, where: str) -> Case:
    """A case is its name, what it expects, and optionally the rest, checked in that order."""
    body = _mapping(
        entry,
        path,
        where,
        required=["name", "expect"],
        optional=["given", "output", "overrides", "setup"],
    )
    name = _parse_name(body["name"], path, where)
    output = _parse_output(body.get("output", Output.EXPRESSION.label), path, where)
    overrides = (
        _parse_overrides(body["overrides"], path, f"{where}.overrides")
        if "overrides" in body
        else Overrides()
    )
    arguments, inputs = _parse_given(body["given"], path, where) if "given" in body else ({}, ())
    expect = _parse_expect(body["expect"], path, where)
    warning = _parse_warning(body["expect"], path, where)
    query = _parse_query(body["expect"], path, where)
    if query is not None and "output" in body:
        raise _fail(
            path,
            f"{where}.output",
            "is for a macro whose text is the result; with expect.query the macro is run for "
            "what it does and the query is what is compared, so give one or the other",
        )
    setup = _parse_setup(body["setup"], path, where) if "setup" in body else ()
    return Case(
        name=name,
        arguments=arguments,
        expect=expect,
        output=output,
        overrides=overrides,
        warning=warning,
        setup=setup,
        query=query,
        inputs=inputs,
    )
