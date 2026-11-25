from pathlib import Path
from typing import Any

import yaml


def installed_packages_dir(raw_config: dict[str, Any], root: Path) -> Path | None:
    """The real project's installed packages, when there are some to reuse.

    Reused only if the project has a packages.yml: dbt compares the number of
    packages it specifies with the number installed, so a leftover directory
    next to no packages.yml would make it stop.
    """
    if not (root / "packages.yml").is_file():
        return None
    directory: Path = (root / raw_config.get("packages-install-path", "dbt_packages")).resolve()
    if directory.is_dir() and any(directory.iterdir()):
        return directory
    return None


def with_absolute_local_paths(packages_yml: str, root: Path) -> str:
    """packages.yml with every relative `local:` path made absolute.

    dbt resolves a `local:` path against the project it runs in, which is the
    generated one. Text that cannot be read as YAML (it may use Jinja) is
    returned untouched, as is text with nothing to change.
    """
    try:
        data = yaml.safe_load(packages_yml)
    except yaml.YAMLError:
        return packages_yml
    if not isinstance(data, dict) or not isinstance(data.get("packages"), list):
        return packages_yml

    changed = False
    for entry in data["packages"]:
        if isinstance(entry, dict) and isinstance(entry.get("local"), str):
            if not Path(entry["local"]).is_absolute():
                entry["local"] = str((root / entry["local"]).resolve())
                changed = True
    return yaml.safe_dump(data, sort_keys=False) if changed else packages_yml
