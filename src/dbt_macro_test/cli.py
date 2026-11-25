import os
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import click

from dbt_macro_test.engine import (
    DbtError,
    RunOutcome,
    check_arguments,
    read_project_config,
    run_unit_tests,
)
from dbt_macro_test.project import (
    FixtureError,
    ProfilesChoice,
    ProjectNotFoundError,
    carried_over,
    generate_project,
    installed_packages_dir,
    macro_directories,
    resolve_profiles_dir,
    resolve_project_root,
)
from dbt_macro_test.spec import SpecError, SpecFile, case_ids, load_specs, select_cases


class CouldNotRun(click.ClickException):
    """The tests could not be run at all, as opposed to a case failing (exit code 1)."""

    exit_code = 2


@contextmanager
def _workspace(keep: bool) -> Iterator[Path]:
    """A fresh directory for the generated project, removed afterwards unless kept."""
    if keep:
        yield Path(tempfile.mkdtemp(prefix="dbt-macro-test-"))
    else:
        with tempfile.TemporaryDirectory(
            prefix="dbt-macro-test-", ignore_cleanup_errors=True
        ) as directory:
            yield Path(directory)


@click.group()
def main() -> None:
    """Unit tests for dbt macros."""


@main.command()
@click.argument(
    "path",
    required=False,
    type=click.Path(exists=True, path_type=Path, resolve_path=True),
)
@click.option(
    "--project-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path, resolve_path=True),
    help="The dbt project. Defaults to the nearest one at or above PATH.",
)
@click.option(
    "--profiles-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help=(
        "Directory with profiles.yml. Defaults to $DBT_PROFILES_DIR, then the project's own "
        "profiles.yml, then dbt's default location."
    ),
)
@click.option("--target", help="The profile target to run against.")
@click.option(
    "--select",
    "selectors",
    multiple=True,
    help=(
        "Run only the cases that match: a macro name, or macro::case. * and ? stand for any "
        "characters, and the option can be given more than once."
    ),
)
@click.option(
    "--list",
    "list_only",
    is_flag=True,
    help="Print the cases that would run, as macro::case, and stop.",
)
@click.option(
    "--keep-generated",
    is_flag=True,
    help="Keep the generated dbt project (a temporary directory) and print where it is.",
)
@click.option("--verbose", is_flag=True, help="Say what is carried over from the project.")
def run(
    path: Path | None,
    project_dir: Path | None,
    profiles_dir: Path | None,
    target: str | None,
    selectors: tuple[str, ...],
    list_only: bool,
    keep_generated: bool,
    verbose: bool,
) -> None:
    """Run the macro tests in PATH: a spec file or a directory (default: macro_test/).

    Exit code 0 means every case passed, 1 that a case failed or errored, and 2
    that the tests could not be run (an invalid spec, a wrong argument, no
    project, dbt itself failing, or nothing matching --select).
    """
    root, path = _locate(project_dir, path)
    spec_files = _load_and_select(path, selectors)
    if list_only:
        for identifier in case_ids(spec_files):
            click.echo(identifier)
        return

    raw_config = read_project_config(root)
    _check_arguments(spec_files, raw_config, root)

    profiles = resolve_profiles_dir(profiles_dir, root, os.environ)
    packages_dir = installed_packages_dir(raw_config, root)
    test_dir = path if path.is_dir() else path.parent
    with _workspace(keep_generated) as out_dir:
        project = _generate(root, test_dir, spec_files, raw_config, out_dir, packages_dir)
        if verbose:
            _say_what_is_carried_over(raw_config, root, packages_dir, profiles)
        install = (root / "packages.yml").is_file() and packages_dir is None
        outcome = _run_dbt(project, profiles, target, install)
        _report(outcome, project, keep_generated)
    sys.exit(0 if outcome.passed else 1)


def _locate(project_dir: Path | None, path: Path | None) -> tuple[Path, Path]:
    """The project and the specs to run: both may have to be found."""
    try:
        root = resolve_project_root(project_dir, path if path is not None else Path.cwd())
    except ProjectNotFoundError as e:
        raise CouldNotRun(str(e)) from e
    if path is None:
        path = root / "macro_test"
        if not path.exists():
            raise CouldNotRun(f"{path} does not exist; put the specs there or give their path")
    return root, path


def _load_and_select(path: Path, selectors: tuple[str, ...]) -> list[SpecFile]:
    """The specs at `path` reduced to the cases the selectors pick."""
    try:
        spec_files = load_specs(path)
    except SpecError as e:
        raise CouldNotRun(str(e)) from e
    everything = case_ids(spec_files)
    spec_files = select_cases(spec_files, selectors)
    chosen = case_ids(spec_files)
    if not chosen:
        raise CouldNotRun(
            f"no case matches {', '.join(selectors)}; the cases are: {', '.join(everything)}"
        )
    if selectors:
        click.echo(f"Selected {len(chosen)} of {len(everything)} cases.", err=True)
    return spec_files


def _check_arguments(spec_files: list[SpecFile], raw_config: dict[str, Any], root: Path) -> None:
    problems = check_arguments(spec_files, macro_directories(raw_config, root))
    if problems:
        raise CouldNotRun("\n".join(problems))


def _say_what_is_carried_over(
    raw_config: dict[str, Any], root: Path, packages_dir: Path | None, profiles: ProfilesChoice
) -> None:
    click.echo("Carried over from the project:", err=True)
    for line in carried_over(raw_config, root, packages_dir):
        click.echo(f"  {line}", err=True)
    click.echo(f"  profiles.yml from: {profiles.source}", err=True)


def _run_dbt(
    project: Path, profiles: ProfilesChoice, target: str | None, install_packages: bool
) -> RunOutcome:
    try:
        return run_unit_tests(
            project,
            profiles_dir=profiles.directory,
            target=target,
            install_packages=install_packages,
        )
    except DbtError as e:
        raise CouldNotRun(f"{e.command} could not run; see dbt's message above") from e


def _report(outcome: RunOutcome, project: Path, keep_generated: bool) -> None:
    for model in outcome.errored_models:
        sql = (project / "models" / f"{model}.sql").read_text().strip()
        click.echo(f"\nSQL generated for the case that errored ({model}):\n  {sql}", err=True)
    click.echo(f"\n{outcome.summary()}", err=True)
    if keep_generated:
        click.echo(f"Generated project kept at {project}", err=True)


def _generate(
    root: Path,
    test_dir: Path,
    spec_files: list[SpecFile],
    raw_config: dict[str, Any],
    out_dir: Path,
    packages_dir: Path | None,
) -> Path:
    try:
        return generate_project(root, test_dir, spec_files, raw_config, out_dir, packages_dir)
    except FixtureError as e:
        raise CouldNotRun(str(e)) from e
