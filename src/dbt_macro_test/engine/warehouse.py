from pathlib import Path
from typing import Any

from dbt.contracts.graph.manifest import Manifest


def connect_project(project_dir: str | Path, profiles_dir: str | Path | None = None) -> str:
    """Parse a real dbt project -- reading its actual profiles.yml -- and
    register its adapter for execute_sql(). Returns the adapter type name
    (e.g. "duckdb", "snowflake") to pass to execute_sql().

    This talks to the project's real configured warehouse the same way
    `dbt run`/`dbt run-operation` would; it's the heavyweight, opt-in tier
    for asserting a macro's rendered SQL actually computes the right value,
    not just that it renders the expected text.
    """
    from dbt_macro_test.engine.runner import invoke_dbt

    args = ["parse", "--quiet", "--project-dir", str(project_dir)]
    if profiles_dir is not None:
        args += ["--profiles-dir", str(profiles_dir)]

    result = invoke_dbt(args)
    if not result.success:
        raise RuntimeError(f"dbt parse failed for {project_dir}: {result.exception}")
    manifest = result.result
    if not isinstance(manifest, Manifest) or manifest.metadata.adapter_type is None:
        raise RuntimeError(f"dbt parse of {project_dir} did not report an adapter type")
    return manifest.metadata.adapter_type


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
