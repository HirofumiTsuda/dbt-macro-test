from pathlib import Path

from dbt_macro_test import execute_sql, load_macro

FIXTURE = Path(__file__).parent / "fixtures" / "macros" / "safe_divide.sql"


def test_macro_sql_executes_correctly_against_real_warehouse(sample_adapter_type):
    safe_divide = load_macro(FIXTURE, "safe_divide")

    rendered = safe_divide("10", "4").strip()
    assert execute_sql(sample_adapter_type, f"select {rendered} as result") == 2.5

    rendered_zero = safe_divide("10", "0").strip()
    assert execute_sql(sample_adapter_type, f"select {rendered_zero} as result") is None
