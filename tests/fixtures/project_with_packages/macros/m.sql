{% macro greet() %}'{{ spike_utils.hello("a") }}'{% endmacro %}
{% macro doubled(x) %}{{ spike_utils.pkg_double(x) }}{% endmacro %}
{% macro duckdb__hello(x) %}user:{{ x }}{% endmacro %}
