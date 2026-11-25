import ast
from pathlib import Path

import pytest

import dbt_macro_test

PACKAGE = Path(dbt_macro_test.__file__).parent
DBT_PACKAGES = {"dbt", "dbt_common"}


def imported_roots(path: Path) -> set[str]:
    """The top-level names a module imports, read from its source rather than by importing it."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module.split(".")[0])
    return found


def modules_outside(directory: str) -> list[Path]:
    return sorted(p for p in PACKAGE.rglob("*.py") if directory not in p.relative_to(PACKAGE).parts)


def test_only_the_engine_imports_dbt() -> None:
    offenders = {
        str(p.relative_to(PACKAGE)): sorted(imported_roots(p) & DBT_PACKAGES)
        for p in modules_outside("engine")
        if imported_roots(p) & DBT_PACKAGES
    }

    assert offenders == {}


def test_the_engine_is_where_dbt_is_imported() -> None:
    engine_modules = sorted((PACKAGE / "engine").glob("*.py"))

    assert any(imported_roots(p) & DBT_PACKAGES for p in engine_modules)


@pytest.mark.parametrize("directory", ["spec", "project"])
def test_spec_and_project_do_not_reach_into_the_engine(directory: str) -> None:
    offenders = [
        str(p.relative_to(PACKAGE))
        for p in (PACKAGE / directory).glob("*.py")
        if "dbt_macro_test.engine" in p.read_text()
    ]

    assert offenders == []


def test_the_public_names_are_still_importable_from_the_package() -> None:
    for name in ("load_macro", "load_macro_from_manifest", "connect_project", "execute_sql"):
        assert callable(getattr(dbt_macro_test, name))
