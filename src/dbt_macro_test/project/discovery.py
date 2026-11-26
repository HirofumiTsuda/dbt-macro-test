from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

import yaml


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


def target_adapter(
    profiles_dir: Path | None,
    environ: Mapping[str, str],
    profile: str | None,
    target: str | None,
) -> str | None:
    """The adapter (the `type` of the target in profiles.yml) that a run would use, or None.

    Read from profiles.yml as it is written, where `profiles_dir` is the one that
    `resolve_profiles_dir` chose (None: DBT_PROFILES_DIR, or dbt's own default). The target is the
    one asked for, or the profile's own `target`. It is None when the file or the profile is not
    there, or when the target or its `type` is a Jinja expression, which this does not render.
    """
    directory = profiles_dir
    if directory is None:
        directory = Path(environ["DBT_PROFILES_DIR"]) if environ.get("DBT_PROFILES_DIR") else None
    if directory is None:
        directory = Path.home() / ".dbt"
    path = directory / "profiles.yml"
    try:
        data = yaml.safe_load(path.read_text())
        entry = data[profile]
        name = target or entry["target"]
        adapter = entry["outputs"][name]["type"]
    except (OSError, yaml.YAMLError, KeyError, TypeError):
        return None
    if not isinstance(adapter, str) or "{{" in adapter or "{{" in str(name):
        return None
    return adapter.strip().lower()
