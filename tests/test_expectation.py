from dbt_macro_test.spec import FixtureRef, InlineRows


def test_inline_dict_rows_are_given_to_dbt_with_their_format() -> None:
    expect = InlineRows("dict", [{"id": 1}])

    assert expect.for_unit_test({}) == {"format": "dict", "rows": [{"id": 1}]}


def test_inline_text_rows_keep_their_format() -> None:
    assert InlineRows("csv", "a\n1\n").for_unit_test({}) == {"format": "csv", "rows": "a\n1\n"}
    assert InlineRows("sql", "select 1 as a").for_unit_test({}) == {
        "format": "sql",
        "rows": "select 1 as a",
    }


def test_a_fixture_gives_its_name_and_the_format_its_file_has() -> None:
    expect = FixtureRef("numbers")

    assert expect.for_unit_test({"numbers": "csv", "other": "sql"}) == {
        "format": "csv",
        "fixture": "numbers",
    }


def test_only_a_fixture_names_a_fixture() -> None:
    assert InlineRows("dict", []).fixture_name is None
    assert FixtureRef("numbers").fixture_name == "numbers"
