{% macro with_alias(x) %}{{ x }} as amount{% endmacro %}
{% macro two_columns(a, b) %}{{ a }} as first, {{ b }} as second{% endmacro %}
