from pathlib import Path
from typing import Any

import yaml


def write_spec(
    directory: Path,
    file_name: str,
    macro: str,
    case: str,
    *,
    rows: list[dict[str, Any]],
    arguments: dict[str, Any] | None = None,
    output: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> Path:
    """Write a spec file with one macro and one case, from the parts of the case."""
    body: dict[str, Any] = {"name": case}
    if arguments is not None:
        body["given"] = {"arguments": arguments}
    if output is not None:
        body["output"] = output
    if overrides is not None:
        body["overrides"] = overrides
    body["expect"] = {"rows": rows}

    spec = {"macros": [{"macro": macro, "cases": [body]}]}
    path = directory / file_name
    path.write_text(yaml.safe_dump(spec, sort_keys=False))
    return path
