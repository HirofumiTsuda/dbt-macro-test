import pytest

from dbt_macro_test.spec import SetupRelation
from dbt_macro_test.spec.setup import rows_to_select, sql_value


def test_numbers_booleans_and_null_are_written_as_they_are() -> None:
    assert [sql_value(v) for v in (1, -2, 2.5, True, False, None)] == [
        "1",
        "-2",
        "2.5",
        "true",
        "false",
        "null",
    ]


def test_a_string_is_quoted_by_dbts_own_macro_so_that_each_adapter_may_escape_it() -> None:
    assert sql_value("it's") == """'{{ dbt.escape_single_quotes("it's") }}'"""


def test_a_string_with_a_double_quote_and_a_line_break_stays_one_jinja_literal() -> None:
    assert sql_value('a "b"\nc') == """'{{ dbt.escape_single_quotes("a \\"b\\"\\nc") }}'"""


def test_rows_become_one_select_with_union_all() -> None:
    assert rows_to_select([{"id": 1, "v": None}, {"id": 2, "v": True}]) == (
        "select 1 as id, null as v\nunion all\nselect 2, true"
    )


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ([{"id": 1}, {"id": 2, "v": 3}], "row 1 has the columns"),
        ([{"a b": 1}], "is not a column name"),
        ([{"1a": 1}], "is not a column name"),
        ([{"id": float("nan")}], "cannot write"),
        ([{"id": [1, 2]}], "cannot write a list in rows; use `sql` for it"),
    ],
)
def test_rows_that_cannot_be_written_are_refused_with_the_reason(
    rows: list[dict[str, object]], message: str
) -> None:
    with pytest.raises((ValueError, TypeError), match=message):
        rows_to_select(rows)


def test_a_relation_filled_by_sql_gives_its_select_as_written() -> None:
    assert SetupRelation("t", sql="  select 1 as id  ").select_sql() == "select 1 as id"


def test_a_relation_filled_by_rows_gives_the_select_of_the_rows() -> None:
    relation = SetupRelation("t", rows=({"id": 1},))

    assert relation.select_sql() == "select 1 as id"
