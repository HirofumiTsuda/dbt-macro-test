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
    RawRun,
    RunOutcome,
    Verdict,
    check_arguments,
    drop_relations,
    invoke_unit_tests,
    judge_error,
    judge_warning,
    read_project_config,
    run_deps,
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
from dbt_macro_test.spec import (
    Case,
    ExpectedError,
    SpecError,
    SpecFile,
    case_id,
    case_ids,
    load_specs,
    select_cases,
    split_isolated,
)


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
    install = (root / "packages.yml").is_file() and packages_dir is None
    together, alone = split_isolated(spec_files)
    with _workspace(keep_generated) as out_dir:
        if verbose:
            _say_what_is_carried_over(raw_config, root, packages_dir, profiles)
        outcome = RunOutcome(passed=True)
        project = out_dir
        if together:
            _generate(root, test_dir, together, raw_config, project, packages_dir)
            outcome = _run_dbt(project, profiles, target, install)
            _warn_left_behind(outcome.left_behind)
            _report_errors(outcome, project)
        verdicts = [
            _run_alone(
                i,
                spec,
                (root, test_dir, raw_config, out_dir, packages_dir),
                profiles,
                target,
                install,
            )
            for i, spec in enumerate(alone)
        ]
        _report(outcome, verdicts, out_dir if keep_generated else None)
    passed = outcome.passed and all(v.passed for _, v in verdicts)
    sys.exit(0 if passed else 1)


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


def _warn_left_behind(names: list[str]) -> None:
    """The relations that cases made and that could not be dropped: they may be in the warehouse."""
    if names:
        click.echo(
            "\nThese relations made by the cases could not be dropped and may be left in the "
            f"warehouse: {', '.join(names)}",
            err=True,
        )


def _report_errors(outcome: RunOutcome, project: Path) -> None:
    """The SQL generated for each case that errored without being expected to."""
    for model in outcome.errored_models:
        sql = (project / "models" / f"{model}.sql").read_text().strip()
        click.echo(f"\nSQL generated for the case that errored ({model}):\n  {sql}", err=True)


def _judge(case: Case, raw: RawRun) -> Verdict:
    """What came of a case that ran alone: it expected an error, or a warning with its rows."""
    if isinstance(case.expect, ExpectedError):
        return judge_error(case.expect.message, raw)
    assert case.warning is not None, "a case runs alone only to give an error or a warning"
    return judge_warning(case.warning.message, raw)


def _run_alone(
    index: int,
    spec: SpecFile,
    generation: tuple[Path, Path, dict[str, Any], Path, Path | None],
    profiles: ProfilesChoice,
    target: str | None,
    install_packages: bool,
) -> tuple[str, Verdict]:
    """Run the one case of `spec` in a dbt run of its own, and judge what came of it."""
    root, test_dir, raw_config, out_dir, packages_dir = generation
    (macro_spec,) = spec.macros
    (case,) = macro_spec.cases
    project = out_dir / "cases-run-alone" / str(index)
    _generate(root, test_dir, [spec], raw_config, project, packages_dir)
    try:
        if install_packages:
            run_deps(project, profiles_dir=profiles.directory, target=target)
        raw = invoke_unit_tests(project, profiles_dir=profiles.directory, target=target, quiet=True)
        _warn_left_behind(
            drop_relations(project, raw.relations, profiles_dir=profiles.directory, target=target)
        )
    except DbtError as e:
        raise CouldNotRun(f"{e.command} could not run; see dbt's message above") from e
    return case_id(macro_spec.macro, case.name), _judge(case, raw)


def _report(outcome: RunOutcome, verdicts: list[tuple[str, Verdict]], kept: Path | None) -> None:
    """The cases that ran alone, then the summary of all of them, then where the project is."""
    for identifier, verdict in verdicts:
        word = "PASS" if verdict.passed else "FAIL"
        click.echo(f"{word} {identifier}: {verdict.detail}", err=True)
    counts = dict(outcome.counts)
    for _, verdict in verdicts:
        key = "pass" if verdict.passed else "fail"
        counts[key] = counts.get(key, 0) + 1
    click.echo(f"\n{RunOutcome(passed=True, counts=counts).summary()}", err=True)
    if kept is not None:
        click.echo(f"Generated project kept at {kept}", err=True)


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
