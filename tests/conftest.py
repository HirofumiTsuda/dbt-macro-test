import os
import subprocess
import sys
from pathlib import Path

import pytest

from dbt_macro_test import connect_project

SAMPLE_PROJECT = Path(__file__).parent.parent / "dev" / "sample_project"


@pytest.fixture(scope="session")
def sample_manifest_path() -> Path:
    subprocess.run(
        [sys.executable, "-m", "dbt.cli.main", "parse"],
        cwd=SAMPLE_PROJECT,
        env={**os.environ, "DBT_PROFILES_DIR": str(SAMPLE_PROJECT)},
        check=True,
        capture_output=True,
    )
    return SAMPLE_PROJECT / "target" / "manifest.json"


@pytest.fixture(scope="session")
def sample_adapter_type() -> str:
    return connect_project(SAMPLE_PROJECT, profiles_dir=SAMPLE_PROJECT)
