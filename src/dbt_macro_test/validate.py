from collections.abc import Collection
from pathlib import Path

from dbt_macro_test.signature import find_signatures, problems_with
from dbt_macro_test.spec import SpecFile


def check_arguments(spec_files: list[SpecFile], macro_dirs: Collection[Path]) -> list[str]:
    """Problems with the arguments the specs pass, found before dbt is run.

    Only macros defined in the project's own macro directories are checked,
    and only when the name is defined once. A macro from a package, a
    qualified name or an unknown name is passed through to dbt.
    """
    definitions = find_signatures(macro_dirs)
    problems = []
    for spec_file in spec_files:
        for macro_spec in spec_file.macros:
            found = definitions.get(macro_spec.macro, [])
            if len(found) != 1:
                continue
            for case in macro_spec.cases:
                for problem in problems_with(found[0], list(case.arguments)):
                    problems.append(
                        f"{spec_file.path}: macro {macro_spec.macro!r}, case {case.name!r}: "
                        f"{problem}"
                    )
    return problems
