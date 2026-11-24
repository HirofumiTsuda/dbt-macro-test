from pathlib import Path


class ProjectNotFoundError(Exception):
    """No dbt_project.yml was found at or above a path."""


def find_project_root(start: Path) -> Path:
    """The nearest directory at or above `start` that contains dbt_project.yml."""
    start = start.resolve()
    for directory in [start, *start.parents]:
        if (directory / "dbt_project.yml").is_file():
            return directory
    raise ProjectNotFoundError(f"no dbt_project.yml found at or above {start}")
