import re
import shutil
from pathlib import Path
from typing import Any

import yaml

from dbt_macro_test.project.fixtures import Fixture, find_fixtures
from dbt_macro_test.project.packages import with_absolute_local_paths
from dbt_macro_test.spec import SpecFile, to_jinja_literal


def macro_directories(raw: dict[str, Any], root: Path) -> list[Path]:
    """The real project's macro directories, as absolute paths."""
    return [(root / p).resolve() for p in raw.get("macro-paths", ["macros"])]


def project_config(
    raw: dict[str, Any],
    root: Path,
    packages_dir: Path | None = None,
    has_fixtures: bool = False,
) -> dict[str, Any]:
    """The generated project's dbt_project.yml, derived from the real project's.

    Everything is kept (name, profile, vars, dispatch, ...) except the paths,
    which point at the real macros and at nothing else, and the run hooks,
    which would otherwise run on every `dbt test`. Packages are either looked
    for in `packages_dir`, the real project's installed ones, or installed
    afresh into the generated project's own directory.
    """
    config = dict(raw)
    config["model-paths"] = ["models"]
    config["macro-paths"] = [str(p) for p in macro_directories(raw, root)]
    for key in ("seed-paths", "snapshot-paths", "analysis-paths"):
        config[key] = []
    config["test-paths"] = ["tests"] if has_fixtures else []
    config.pop("on-run-start", None)
    config.pop("on-run-end", None)
    if packages_dir is not None:
        config["packages-install-path"] = str(packages_dir)
    else:
        config.pop("packages-install-path", None)
    return config


def macro_call(macro: str, arguments: dict[str, Any]) -> str:
    args = ", ".join(f"{name}={to_jinja_literal(value)}" for name, value in arguments.items())
    return f"{macro}({args})"


def model_name(spec_path: Path, test_dir: Path, macro: str, case: str) -> str:
    relative = spec_path.relative_to(test_dir).with_suffix("")
    return re.sub(r"\W", "_", f"_mt_{relative.as_posix()}_{macro}_{case}")


def build_files(
    raw_config: dict[str, Any],
    root: Path,
    test_dir: Path,
    spec_files: list[SpecFile],
    packages_yml: str | None = None,
    packages_dir: Path | None = None,
    fixtures: dict[str, Fixture] | None = None,
) -> dict[str, str]:
    """The generated project, as relative path -> file content."""
    fixtures = fixtures or {}
    fixture_formats = {name: fixture.format for name, fixture in fixtures.items()}
    files: dict[str, str] = {
        "dbt_project.yml": yaml.safe_dump(
            project_config(raw_config, root, packages_dir, bool(fixtures)), sort_keys=False
        )
    }
    for fixture in fixtures.values():
        files[f"tests/fixtures/{fixture.file_name}"] = fixture.text
    if packages_yml is not None:
        files["packages.yml"] = with_absolute_local_paths(packages_yml, root)

    unit_tests: list[dict[str, Any]] = []
    for spec_file in spec_files:
        for macro_spec in spec_file.macros:
            for case in macro_spec.cases:
                name = model_name(spec_file.path, test_dir, macro_spec.macro, case.name)
                call = macro_call(macro_spec.macro, case.arguments)
                path = f"models/{name}.sql"
                if path in files:
                    raise ValueError(f"{spec_file.path}: {name} is generated more than once")
                files[path] = case.output.model_sql(call)
                unit_test: dict[str, Any] = {"name": case.name, "model": name}
                if case.overrides:
                    unit_test["overrides"] = case.overrides
                unit_test["given"] = []
                unit_test["expect"] = case.expect.for_unit_test(fixture_formats)
                unit_tests.append(unit_test)
    files["models/_unit_tests.yml"] = yaml.safe_dump({"unit_tests": unit_tests}, sort_keys=False)
    return files


def write_project(files: dict[str, str], out_dir: Path) -> None:
    shutil.rmtree(out_dir, ignore_errors=True)
    for relative, content in files.items():
        target = out_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)


def carried_over(
    raw_config: dict[str, Any], root: Path, packages_dir: Path | None = None
) -> list[str]:
    """What the generated project takes from the real project, for `--verbose`."""
    variables = raw_config.get("vars") or {}
    hooks = [key for key in ("on-run-start", "on-run-end") if key in raw_config]
    lines = [
        f"project: {raw_config.get('name')} (profile: {raw_config.get('profile')})",
        "macro directories: " + ", ".join(str(p) for p in macro_directories(raw_config, root)),
        "vars: " + (", ".join(sorted(str(k) for k in variables)) or "none"),
        f"dispatch entries: {len(raw_config.get('dispatch') or [])}",
        _packages_line(root, packages_dir),
        "run hooks left out: " + (", ".join(hooks) or "none"),
    ]
    return lines


def _packages_line(root: Path, packages_dir: Path | None) -> str:
    if packages_dir is not None:
        return f"packages: reusing {packages_dir} (dbt deps is not run)"
    if (root / "packages.yml").is_file():
        return "packages: packages.yml copied (dbt deps is run)"
    return "packages: none"


def generate_project(
    root: Path,
    test_dir: Path,
    spec_files: list[SpecFile],
    raw_config: dict[str, Any],
    out_dir: Path,
    packages_dir: Path | None = None,
) -> Path:
    """Write the generated project into `out_dir` and return it."""
    packages = root / "packages.yml"
    test_dir = test_dir.resolve()
    files = build_files(
        raw_config,
        root,
        test_dir,
        spec_files,
        packages.read_text() if packages.is_file() else None,
        packages_dir,
        find_fixtures(spec_files, test_dir),
    )
    write_project(files, out_dir)
    return out_dir
