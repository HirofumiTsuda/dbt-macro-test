from pathlib import Path
from typing import Any

from dbt.config.project import load_raw_project


def read_project_config(root: Path) -> dict[str, Any]:
    """The project's dbt_project.yml as dbt reads it, before Jinja is rendered."""
    return load_raw_project(str(root))
