{% macro hello(x) %}{{ return(adapter.dispatch('hello', 'spike_utils')(x)) }}{% endmacro %}
{% macro default__hello(x) %}default:{{ x }}{% endmacro %}
{% macro duckdb__hello(x) %}duckdb:{{ x }}{% endmacro %}
{% macro pkg_double(x) %}({{ x }} * 2){% endmacro %}
