import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from dbt_macro_test import connect_project

SAMPLE_PROJECT = Path(__file__).parent.parent / "dev" / "sample_project"


@pytest.fixture(scope="session")
def sample_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A copy of dev/sample_project for this test process.

    dbt writes target/ and logs/ into the project it parses, so the tests run in parallel must
    not share one directory.
    """
    copy = tmp_path_factory.mktemp("sample_project") / "sample_project"
    shutil.copytree(SAMPLE_PROJECT, copy, ignore=shutil.ignore_patterns("target", "logs"))
    return copy


@pytest.fixture(scope="session")
def sample_manifest_path(sample_project: Path) -> Path:
    subprocess.run(
        [sys.executable, "-m", "dbt.cli.main", "parse"],
        cwd=sample_project,
        env={**os.environ, "DBT_PROFILES_DIR": str(sample_project)},
        check=True,
        capture_output=True,
    )
    return sample_project / "target" / "manifest.json"


@pytest.fixture(scope="session")
def sample_adapter_type(sample_project: Path) -> str:
    return connect_project(sample_project, profiles_dir=sample_project)
