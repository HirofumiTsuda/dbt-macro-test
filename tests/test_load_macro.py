from pathlib import Path

import pytest

from dbt_macro_test import load_macro, load_macro_from_manifest

FIXTURE = Path(__file__).parent / "fixtures" / "macros" / "greeting.sql"


def test_pure_jinja_macro():
    greeting = load_macro(FIXTURE, "greeting")
    assert greeting("World") == "Hello, World! default_country=JP"


def test_macro_with_var_override():
    greeting = load_macro(FIXTURE, "greeting", context={"var": lambda name, default=None: "US"})
    assert greeting("World") == "Hello, World! default_country=US"


def test_generate_schema_name_override():
    fn = load_macro(
        FIXTURE, "generate_schema_name", context={"default_schema": "analytics"}
    )
    assert fn(None, node=None).strip() == "analytics"
    assert fn("staging", node=None).strip() == "staging"


def test_macro_not_found_raises():
    with pytest.raises(ValueError, match="not found"):
        load_macro(FIXTURE, "does_not_exist")


def test_ref_without_stub_raises_clear_error():
    fn = load_macro(FIXTURE.parent / "uses_ref.sql", "uses_ref")
    with pytest.raises(RuntimeError, match="ref"):
        fn()


def test_load_from_manifest(sample_manifest_path):
    greeting = load_macro_from_manifest(sample_manifest_path, "macro.sample_project.greeting")
    assert greeting("World") == "Hello, World! default_country=JP"
