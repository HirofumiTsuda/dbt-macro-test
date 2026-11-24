import json
from pathlib import Path
from typing import Any, Callable

from dbt.clients.jinja import MacroGenerator
from dbt.node_types import NodeType
from dbt.parser.macros import Macro
from dbt_common.clients import jinja as jinja_common

_DEFAULT_CONTEXT: dict[str, Any] = {
    "var": lambda name, default=None: default,
    "config": lambda *args, **kwargs: "",
    "log": lambda *args, **kwargs: None,
}


def _missing_dependency(name: str) -> Callable[..., Any]:
    def _raise(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError(
            f"macro under test calls {name}(), which has no default stub -- "
            f"pass context={{'{name}': ...}} to load_macro() yourself"
        )

    return _raise


for _dep_name in ("ref", "source"):
    _DEFAULT_CONTEXT[_dep_name] = _missing_dependency(_dep_name)


def load_macro(
    path: str | Path, name: str, context: dict[str, Any] | None = None
) -> Callable[..., Any]:
    """Load a single macro from a .sql file and return it as a callable."""
    raw_code = Path(path).read_text()

    blocks = [
        block
        for block in jinja_common.extract_toplevel_blocks(
            raw_code, allowed_blocks={"macro"}, collect_raw_data=False
        )
        if isinstance(block, jinja_common.BlockTag)
    ]
    matches = [b for b in blocks if b.block_name == name]
    if not matches:
        found = [b.block_name for b in blocks]
        raise ValueError(f"macro {name!r} not found in {path} (found: {found})")

    macro = Macro(
        path=str(path),
        macro_sql=matches[0].full_block,
        original_file_path=str(path),
        package_name="dbt_macro_test",
        resource_type=NodeType.Macro,
        name=name,
        unique_id=f"macro.dbt_macro_test.{name}",
    )

    return _wrap(macro, context)


def load_macro_from_manifest(
    manifest_path: str | Path, unique_id: str, context: dict[str, Any] | None = None
) -> Callable[..., Any]:
    """Load a single macro out of an already-generated dbt manifest.json.

    Faster than load_macro() for block-extraction (dbt already did it) and
    the entry point ref()/source() resolution would build on later -- but
    requires the caller to have run `dbt parse`/`dbt compile` first, and the
    manifest can go stale if the macro's source changed since.
    """
    manifest = json.loads(Path(manifest_path).read_text())
    try:
        node = manifest["macros"][unique_id]
    except KeyError:
        raise ValueError(
            f"macro {unique_id!r} not found in manifest {manifest_path}"
        ) from None

    macro = Macro(
        path=node["path"],
        macro_sql=node["macro_sql"],
        original_file_path=node["original_file_path"],
        package_name=node["package_name"],
        resource_type=NodeType.Macro,
        name=node["name"],
        unique_id=node["unique_id"],
    )
    return _wrap(macro, context)


def _wrap(macro: Macro, context: dict[str, Any] | None) -> Callable[..., Any]:
    merged_context = {**_DEFAULT_CONTEXT, **(context or {})}
    return MacroGenerator(macro, context=merged_context)


def connect_project(project_dir: str | Path, profiles_dir: str | Path | None = None) -> str:
    """Parse a real dbt project -- reading its actual profiles.yml -- and
    register its adapter for execute_sql(). Returns the adapter type name
    (e.g. "duckdb", "snowflake") to pass to execute_sql().

    This talks to the project's real configured warehouse the same way
    `dbt run`/`dbt run-operation` would; it's the heavyweight, opt-in tier
    for asserting a macro's rendered SQL actually computes the right value,
    not just that it renders the expected text.
    """
    from dbt.cli.main import dbtRunner

    args = ["parse", "--quiet", "--project-dir", str(project_dir)]
    if profiles_dir is not None:
        args += ["--profiles-dir", str(profiles_dir)]

    result = dbtRunner().invoke(args)
    if not result.success:
        raise RuntimeError(f"dbt parse failed for {project_dir}: {result.exception}")
    return result.result.metadata.adapter_type


def execute_sql(adapter_type: str, sql: str) -> Any:
    """Run raw SQL against a warehouse connected via connect_project() and
    return the single scalar value (single row, single column), else the
    raw agate Table for multi-row/multi-column results."""
    from dbt.adapters.factory import get_adapter_by_type

    adapter = get_adapter_by_type(adapter_type)
    with adapter.connection_named("dbt_macro_test"):
        _, table = adapter.execute(sql, fetch=True)

    if len(table.rows) == 1 and len(table.columns) == 1:
        return table.rows[0][0]
    return table
