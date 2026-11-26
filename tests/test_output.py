import pytest

from dbt_macro_test.spec import Output


def test_an_expression_is_given_a_column_name() -> None:
    assert Output.EXPRESSION.model_sql("m()") == "select {{ m() }} as result\n"


def test_columns_bring_their_own_names() -> None:
    assert Output.COLUMNS.model_sql("m()") == "select {{ m() }}\n"


def test_a_query_is_the_whole_model() -> None:
    assert Output.QUERY.model_sql("m()") == "{{ m() }}\n"


def test_text_is_returned_as_one_string_without_running_it() -> None:
    assert Output.TEXT.model_sql("m(a=1)") == (
        "select '{{ dbt.escape_single_quotes((m(a=1)) | trim) }}' as result\n"
    )


@pytest.mark.parametrize("member", list(Output))
def test_every_output_can_be_parsed_from_its_label(member: Output) -> None:
    assert Output.parse(member.label) is member


@pytest.mark.parametrize("label", ["nope", "", None, 1])
def test_an_unknown_label_names_the_allowed_ones(label: object) -> None:
    with pytest.raises(ValueError, match="is not one of: expression, columns, query, text"):
        Output.parse(label)
