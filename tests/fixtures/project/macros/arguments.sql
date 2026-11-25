{% macro add(x, y=5) %}({{ x }} + {{ y }}){% endmacro %}
{% macro table_name(rel) %}'{{ rel.identifier }}'{% endmacro %}
