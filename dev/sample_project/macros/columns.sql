{# The year and the month of a date, as two columns of their own. #}
{% macro date_parts(date_expression) -%}
    extract(year from {{ date_expression }}) as year,
    extract(month from {{ date_expression }}) as month
{%- endmacro %}
