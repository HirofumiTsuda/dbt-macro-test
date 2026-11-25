{% macro positive(x) %}
  {% if x < 0 %}
    {{ exceptions.raise_compiler_error("x must not be negative, got " ~ x) }}
  {% endif %}
  {{ x }}
{% endmacro %}
{% macro guarded_positive(x) %}
  {% if execute and x < 0 %}
    {{ exceptions.raise_compiler_error("guarded: x must not be negative, got " ~ x) }}
  {% endif %}
  {{ x }}
{% endmacro %}
{% macro bad_cast() %}cast('abc' as integer){% endmacro %}
