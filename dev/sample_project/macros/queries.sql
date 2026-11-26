{# The orders of two relations, each once: a whole select. #}
{% macro all_orders(first, second) %}
    select * from {{ first }}
    union
    select * from {{ second }}
{% endmacro %}
