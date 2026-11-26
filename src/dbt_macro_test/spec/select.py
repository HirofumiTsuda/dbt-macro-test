from collections.abc import Collection
from dataclasses import replace
from fnmatch import fnmatchcase
from pathlib import Path

from dbt_macro_test.spec.spec import Case, SpecFile


def case_id(macro: str, case: str) -> str:
    return f"{macro}::{case}"


def _matches(patterns: Collection[str], macro: str, case: str) -> bool:
    """A pattern with `::` is compared with `macro::case`, any other with the macro name."""
    for pattern in patterns:
        target = case_id(macro, case) if "::" in pattern else macro
        if fnmatchcase(target, pattern):
            return True
    return False


def select_cases(spec_files: list[SpecFile], patterns: Collection[str]) -> list[SpecFile]:
    """The specs reduced to the cases that match any pattern; all of them with no pattern."""
    if not patterns:
        return spec_files
    selected = []
    for spec_file in spec_files:
        macros = []
        for macro_spec in spec_file.macros:
            cases = [c for c in macro_spec.cases if _matches(patterns, macro_spec.macro, c.name)]
            if cases:
                macros.append(replace(macro_spec, cases=cases))
        if macros:
            selected.append(replace(spec_file, macros=macros))
    return selected


def split_isolated(spec_files: list[SpecFile]) -> tuple[list[SpecFile], list[SpecFile]]:
    """The specs without the cases that must run alone, and one spec per case that must.

    A case that expects an error is one of those: if it raises where dbt parses the project, no
    other case in the same run gets to run. So is one that expects a warning, which is told from
    the other cases' warnings only when it runs alone. Each of them comes back as a spec of its
    own, with one macro and one case.
    """
    together: list[SpecFile] = []
    alone: list[SpecFile] = []
    for spec_file in spec_files:
        macros = []
        for macro_spec in spec_file.macros:
            kept = [c for c in macro_spec.cases if not c.isolated]
            if kept:
                macros.append(replace(macro_spec, cases=kept))
            for case in macro_spec.cases:
                if case.isolated:
                    one = replace(macro_spec, cases=[case])
                    alone.append(replace(spec_file, macros=[one]))
        if macros:
            together.append(replace(spec_file, macros=macros))
    return together, alone


def without_case(spec_files: list[SpecFile], macro: str, case: Case, path: Path) -> list[SpecFile]:
    """The specs without one case (the one of that name, under that macro, in the file at `path`),
    and without the macro or the file that it leaves empty."""
    result: list[SpecFile] = []
    for spec_file in spec_files:
        macros = []
        for macro_spec in spec_file.macros:
            if spec_file.path == path and macro_spec.macro == macro:
                kept = [c for c in macro_spec.cases if c.name != case.name]
                macro_spec = replace(macro_spec, cases=kept)
            if macro_spec.cases:
                macros.append(macro_spec)
        if macros:
            result.append(replace(spec_file, macros=macros))
    return result


def case_ids(spec_files: list[SpecFile]) -> list[str]:
    return [
        case_id(macro_spec.macro, case.name)
        for spec_file in spec_files
        for macro_spec in spec_file.macros
        for case in macro_spec.cases
    ]
