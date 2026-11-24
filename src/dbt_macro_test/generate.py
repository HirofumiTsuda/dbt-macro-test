import re
import shutil
from pathlib import Path
from typing import Any

import yaml
from dbt.config.project import load_raw_project

from dbt_macro_test.literals import to_jinja_literal
from dbt_macro_test.spec import SpecFile

GENERATED_DIR = Path("target") / "macro_test"


def project_config(raw: dict[str, Any], root: Path) -> dict[str, Any]:
    """The generated project's dbt_project.yml, derived from the real project's.

    Everything is kept (name, profile, vars, dispatch, ...) except the paths,
    which point at the real macros and at nothing else, and the run hooks,
    which would otherwise run on every `dbt test`.
    """
    config = dict(raw)
    config["model-paths"] = ["models"]
    config["macro-paths"] = [str((root / p).resolve()) for p in raw.get("macro-paths", ["macros"])]
    for key in ("seed-paths", "snapshot-paths", "analysis-paths", "test-paths"):
        config[key] = []
    config.pop("on-run-start", None)
    config.pop("on-run-end", None)
    return config


def macro_call(macro: str, arguments: dict[str, Any]) -> str:
    args = ", ".join(f"{name}={to_jinja_literal(value)}" for name, value in arguments.items())
    return f"{macro}({args})"


def model_sql(call: str, output: str) -> str:
    """The throwaway model: an expression gets a column name, columns bring their own."""
    if output == "columns":
        return f"select {{{{ {call} }}}}\n"
    return f"select {{{{ {call} }}}} as result\n"


def model_name(spec_path: Path, test_dir: Path, macro: str, case: str) -> str:
    relative = spec_path.relative_to(test_dir).with_suffix("")
    return re.sub(r"\W", "_", f"_mt_{relative.as_posix()}_{macro}_{case}")


def build_files(
    raw_config: dict[str, Any],
    root: Path,
    test_dir: Path,
    spec_files: list[SpecFile],
    packages_yml: str | None = None,
) -> dict[str, str]:
    """The generated project, as relative path -> file content."""
    files: dict[str, str] = {
        "dbt_project.yml": yaml.safe_dump(project_config(raw_config, root), sort_keys=False)
    }
    if packages_yml is not None:
        files["packages.yml"] = packages_yml

    unit_tests: list[dict[str, Any]] = []
    for spec_file in spec_files:
        for macro_spec in spec_file.macros:
            for case in macro_spec.cases:
                name = model_name(spec_file.path, test_dir, macro_spec.macro, case.name)
                call = macro_call(macro_spec.macro, case.arguments)
                path = f"models/{name}.sql"
                if path in files:
                    raise ValueError(f"{spec_file.path}: {name} is generated more than once")
                files[path] = model_sql(call, case.output)
                unit_tests.append(
                    {
                        "name": case.name,
                        "model": name,
                        "given": [],
                        "expect": {"rows": case.expect_rows},
                    }
                )
    files["models/_unit_tests.yml"] = yaml.safe_dump({"unit_tests": unit_tests}, sort_keys=False)
    return files


def write_project(files: dict[str, str], out_dir: Path) -> None:
    shutil.rmtree(out_dir, ignore_errors=True)
    for relative, content in files.items():
        target = out_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)


def generate_project(root: Path, test_dir: Path, spec_files: list[SpecFile]) -> Path:
    """Write the generated project under <root>/target/macro_test and return it."""
    packages = root / "packages.yml"
    files = build_files(
        load_raw_project(str(root)),
        root,
        test_dir.resolve(),
        spec_files,
        packages.read_text() if packages.is_file() else None,
    )
    out_dir = root / GENERATED_DIR
    write_project(files, out_dir)
    return out_dir
