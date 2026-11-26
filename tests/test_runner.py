import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from dbt_macro_test.engine import runner
from dbt_macro_test.spec import RELATION_MARK


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


class Event:
    def __init__(self, message: str, level: str = "debug") -> None:
        self.info = SimpleNamespace(msg=message, level=level)


class Fake:
    """A dbt that sends some events to the callbacks and answers with a result."""

    def __init__(self, events: list[Event], success: bool = True, exception: object = None) -> None:
        self.events = events
        self.success = success
        self.exception = exception
        self.callbacks: list[Any] = []

    def __call__(self, callbacks: list[Any] | None = None) -> "Fake":
        self.callbacks = callbacks or []
        return self

    def invoke(self, args: list[str]) -> Any:
        for event in self.events:
            for callback in self.callbacks:
                callback(event)
        return SimpleNamespace(
            success=self.success,
            exception=self.exception,
            result=SimpleNamespace(results=[]),
        )


def mark(identifier: str, schema: str | None = None) -> Event:
    relation = {"database": None, "schema": schema, "identifier": identifier, "type": "table"}
    return Event(f"\x1b[0m10:00:00  {RELATION_MARK}{json.dumps(relation)}")


def test_the_relations_the_models_log_are_collected_once_each(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Fake([mark("a"), mark("b", "s"), mark("a"), Event("[WARNING]: careful", "warn")])
    monkeypatch.setattr(runner, "dbtRunner", fake)

    raw = runner.invoke_unit_tests(tmp_path)

    assert [r["identifier"] for r in raw.relations] == ["a", "b"]
    assert raw.relations[1]["schema"] == "s"
    assert raw.warnings == ["careful"]


def test_a_log_line_of_dbt_that_is_not_a_relation_is_left_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "dbtRunner", Fake([Event("Running with dbt=1.12"), Event("done")]))

    raw = runner.invoke_unit_tests(tmp_path)

    assert (raw.relations, raw.warnings) == ([], [])


def calls_of(monkeypatch: pytest.MonkeyPatch, success: bool = True) -> list[list[str]]:
    calls: list[list[str]] = []

    def invoke(args: list[str], callbacks: Any = None) -> Any:
        calls.append(args)
        return SimpleNamespace(success=success, exception=None if success else "boom")

    monkeypatch.setattr(runner, "invoke_dbt", invoke)
    return calls


def test_the_relations_are_dropped_by_a_run_operation_with_the_names_that_were_logged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = calls_of(monkeypatch)
    relations = [{"database": None, "schema": "s", "identifier": "t1", "type": "table"}]

    left = runner.drop_relations(tmp_path, relations, profiles_dir=tmp_path, target="ci")

    (args,) = calls
    assert args[2:4] == ["run-operation", "_dmt_drop"]
    assert json.loads(args[args.index("--args") + 1]) == {"relations": relations}
    assert args[args.index("--target") + 1] == "ci"
    assert left == []


def test_nothing_is_run_when_no_relation_was_made(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = calls_of(monkeypatch)

    assert runner.drop_relations(tmp_path, []) == []
    assert calls == []


def test_the_names_that_could_not_be_dropped_are_returned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls_of(monkeypatch, success=False)
    relations = [
        {"database": None, "schema": None, "identifier": "t1", "type": "table"},
        {"database": None, "schema": None, "identifier": "t2", "type": "table"},
    ]

    assert runner.drop_relations(tmp_path, relations) == ["t1", "t2"]
