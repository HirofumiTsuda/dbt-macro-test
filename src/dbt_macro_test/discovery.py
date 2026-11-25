from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple


class ProjectNotFoundError(Exception):
    """No dbt_project.yml was found at or above a path."""


def find_project_root(start: Path) -> Path:
    """The nearest directory at or above `start` that contains dbt_project.yml."""
    start = start.resolve()
    for directory in [start, *start.parents]:
        if (directory / "dbt_project.yml").is_file():
            return directory
    raise ProjectNotFoundError(f"no dbt_project.yml found at or above {start}")


def resolve_project_root(project_dir: Path | None, start: Path) -> Path:
    """The project given explicitly, or else the nearest one at or above `start`."""
    if project_dir is None:
        return find_project_root(start)
    project_dir = project_dir.resolve()
    if not (project_dir / "dbt_project.yml").is_file():
        raise ProjectNotFoundError(f"no dbt_project.yml in {project_dir}")
    return project_dir


class ProfilesChoice(NamedTuple):
    directory: Path | None
    source: str


def resolve_profiles_dir(
    flag: Path | None, root: Path, environ: Mapping[str, str]
) -> ProfilesChoice:
    """Where dbt should look for profiles.yml, in the order dbt itself uses.

    The flag comes first, then DBT_PROFILES_DIR (which dbt reads itself, so no
    directory is passed), then profiles.yml in the project, standing in for the
    working directory dbt would look in, and last dbt's own default.
    """
    if flag is not None:
        return ProfilesChoice(flag, "--profiles-dir")
    if environ.get("DBT_PROFILES_DIR"):
        return ProfilesChoice(None, "DBT_PROFILES_DIR")
    if (root / "profiles.yml").is_file():
        return ProfilesChoice(root, "the project")
    return ProfilesChoice(None, "dbt's default location")
