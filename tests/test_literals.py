from typing import Any

import pytest

from dbt_macro_test.spec import JinjaExpression, to_jinja_literal


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "none"),
        (True, "true"),
        (False, "false"),
        (10, "10"),
        (2.5, "2.5"),
        ("World", '"World"'),
        ('say "hi"', '"say \\"hi\\""'),
        ("{{ x }}", '"{{ x }}"'),
        ([1, "a", None], '[1, "a", none]'),
        ({"a": 1, "b": [True]}, '{"a": 1, "b": [true]}'),
    ],
)
def test_value_is_rendered_as_a_jinja_literal(value: Any, expected: str) -> None:
    assert to_jinja_literal(value) == expected


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_non_finite_float_is_rejected(value: float) -> None:
    with pytest.raises(ValueError, match="cannot render"):
        to_jinja_literal(value)


def test_unsupported_type_is_rejected() -> None:
    with pytest.raises(TypeError, match="set"):
        to_jinja_literal({1, 2})


def test_non_string_mapping_key_is_rejected() -> None:
    with pytest.raises(TypeError, match="not a string"):
        to_jinja_literal({1: "a"})


def test_a_jinja_expression_is_passed_through_as_it_is() -> None:
    assert to_jinja_literal(JinjaExpression("api.Relation.create(schema='s')")) == (
        "api.Relation.create(schema='s')"
    )
    assert to_jinja_literal([JinjaExpression("x"), 1]) == "[x, 1]"
