{% macro careful(x) %}
  {% do exceptions.warn("careful: " ~ x) %}
  {{ x }}
{% endmacro %}
