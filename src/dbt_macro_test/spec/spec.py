import re
from collections.abc import Collection
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict

import yaml

from dbt_macro_test.spec.expectation import Expectation, ExpectedError, FixtureRef, InlineRows
from dbt_macro_test.spec.literals import JinjaExpression
from dbt_macro_test.spec.output import Output

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


def _parse_given(value: Any, path: Path, where: str) -> dict[str, Any]:
    """The arguments of the case; `given` may also be left out, or have none."""
    given = _mapping(value, path, f"{where}.given", optional=["arguments"])
    if "arguments" not in given:
        return {}
    arguments = _mapping(given["arguments"], path, f"{where}.given.arguments", any_keys=True)
    for key in arguments:
        if not isinstance(key, str) or not _IDENTIFIER.match(key):
            raise _fail(path, f"{where}.given.arguments", f"{key!r} is not an argument name")
    return {
        key: _parse_argument(argument, path, f"{where}.given.arguments.{key}")
        for key, argument in arguments.items()
    }


def _parse_expect(value: Any, path: Path, where: str) -> Expectation:
    """What a case expects: rows written in it, rows in a fixture file, or an error; one of them."""
    here = f"{where}.expect"
    expect = _mapping(value, path, here, optional=["rows", "format", "fixture", "error"])
    if sum(key in expect for key in ("rows", "fixture", "error")) != 1:
        raise _fail(path, here, "needs exactly one of 'rows', 'fixture' and 'error'")
    if "error" in expect:
        return _parse_error(expect, path, here)
    if "fixture" in expect:
        return _parse_fixture(expect, path, here)
    return _parse_inline_rows(expect, path, here)


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
        entry, path, where, required=["name", "expect"], optional=["given", "output", "overrides"]
    )
    name = _parse_name(body["name"], path, where)
    output = _parse_output(body.get("output", Output.EXPRESSION.label), path, where)
    overrides = (
        _parse_overrides(body["overrides"], path, f"{where}.overrides")
        if "overrides" in body
        else Overrides()
    )
    arguments = _parse_given(body["given"], path, where) if "given" in body else {}
    expect = _parse_expect(body["expect"], path, where)
    return Case(name=name, arguments=arguments, expect=expect, output=output, overrides=overrides)
