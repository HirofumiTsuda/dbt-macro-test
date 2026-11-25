import os
from pathlib import Path
from typing import Any

import pytest

from dbt_macro_test.engine import runner


class MovesAway:
    """A dbt that does what dbt 1.8 does: goes into the project directory and stays there."""

    def __init__(self, project: Path, fail: bool = False) -> None:
        self.project = project
        self.fail = fail
        self.callbacks: list[Any] = []

    def __call__(self, callbacks: list[Any] | None = None) -> "MovesAway":
        self.callbacks = callbacks or []
        return self

    def invoke(self, args: list[str]) -> str:
        os.chdir(self.project)
        if self.fail:
            raise RuntimeError("dbt fell over")
        return "result of " + " ".join(args)


def test_the_working_directory_is_where_it_was_after_dbt_ran(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    here = tmp_path / "here"
    project = tmp_path / "project"
    here.mkdir()
    project.mkdir()
    monkeypatch.chdir(here)
    monkeypatch.setattr(runner, "dbtRunner", MovesAway(project))

    result = runner.invoke_dbt(["test"])

    assert str(result) == "result of test"
    assert Path.cwd() == here


def test_the_working_directory_is_put_back_when_dbt_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    here = tmp_path / "here"
    project = tmp_path / "project"
    here.mkdir()
    project.mkdir()
    monkeypatch.chdir(here)
    monkeypatch.setattr(runner, "dbtRunner", MovesAway(project, fail=True))

    with pytest.raises(RuntimeError, match="dbt fell over"):
        runner.invoke_dbt(["test"])

    assert Path.cwd() == here


def test_the_callbacks_reach_dbt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = MovesAway(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runner, "dbtRunner", fake)
    callback = print

    runner.invoke_dbt(["parse"], [callback])

    assert fake.callbacks == [callback]
