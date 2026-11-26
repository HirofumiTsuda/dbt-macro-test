import re
import secrets
import shutil
import time
from importlib import resources
from pathlib import Path
from typing import Any, NotRequired, TypedDict

import yaml

from dbt_macro_test.project.fixtures import Fixture, find_fixtures
from dbt_macro_test.project.packages import with_absolute_local_paths
from dbt_macro_test.spec import Overrides, SpecFile, UnitTestExpect, to_jinja_literal


class UnitTest(TypedDict):
    """One entry of `unit_tests:` in the generated project."""

    name: str
    model: str
    overrides: NotRequired[Overrides]
    given: list[Any]
    expect: UnitTestExpect


CLEANUP_PATH = "macros/_mt_drop.sql"


def cleanup_macro() -> str:
    """The macro that drops the relations the cases made, which is a file of the package."""
    return resources.files("dbt_macro_test.project").joinpath(CLEANUP_PATH).read_text()


def new_run_id() -> str:
    """What tells the relations of one generated project from another's: a UTC timestamp, and a
    little chance, so that two runs in the same second and the same schema do not meet."""
    return time.strftime("%Y%m%dT%H%M%S", time.gmtime()) + "_" + secrets.token_hex(3)


def macro_directories(raw: dict[str, Any], root: Path) -> list[Path]:
    """The real project's macro directories, as absolute paths."""
    return [(root / p).resolve() for p in raw.get("macro-paths", ["macros"])]


def project_config(
    raw: dict[str, Any],
    root: Path,
    packages_dir: Path | None = None,
    has_fixtures: bool = False,
    has_relations: bool = False,
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
    if has_relations:
        config["macro-paths"].append("macros")  # the generated project's own: _mt_drop
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
    run_id: str = "run",
) -> dict[str, str]:
    """The generated project, as relative path -> file content.

    `run_id` is in the name of every relation that a case makes (`_mt_<run_id>_<n>_<name>`).
    """
    fixtures = fixtures or {}
    fixture_formats = {name: fixture.format for name, fixture in fixtures.items()}
    has_relations = any(
        case.setup for spec_file in spec_files for m in spec_file.macros for case in m.cases
    )
    files: dict[str, str] = {
        "dbt_project.yml": yaml.safe_dump(
            project_config(raw_config, root, packages_dir, bool(fixtures), has_relations),
            sort_keys=False,
        )
    }
    if has_relations:
        files[CLEANUP_PATH] = cleanup_macro()
    for fixture in fixtures.values():
        files[f"tests/fixtures/{fixture.file_name}"] = fixture.text
    if packages_yml is not None:
        files["packages.yml"] = with_absolute_local_paths(packages_yml, root)

    unit_tests: list[UnitTest] = []
    case_number = 0
    for spec_file in spec_files:
        for macro_spec in spec_file.macros:
            for case in macro_spec.cases:
                name = model_name(spec_file.path, test_dir, macro_spec.macro, case.name)
                call = macro_call(macro_spec.macro, case.arguments)
                path = f"models/{name}.sql"
                if path in files:
                    raise ValueError(f"{spec_file.path}: {name} is generated more than once")
                files[path] = case.model_sql(call, f"_mt_{run_id}_{case_number}_")
                case_number += 1
                unit_test = UnitTest(
                    name=case.name,
                    model=name,
                    given=[],
                    expect=case.expect.for_unit_test(fixture_formats),
                )
                if case.overrides:
                    unit_test["overrides"] = case.overrides
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
        new_run_id(),
    )
    write_project(files, out_dir)
    return out_dir
