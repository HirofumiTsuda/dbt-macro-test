{# An amount in cents as dollars, to two places by default. `/ 100.0`, as two integers divide as
   integers on Postgres. #}
{% macro cents_to_dollars(column_name, scale=2) -%}
    ({{ column_name }} / 100.0)::numeric(16, {{ scale }})
{%- endmacro %}

{# A division that gives null, and not an error, when the denominator is zero. #}
{% macro safe_divide(numerator, denominator) -%}
    {{ numerator }} / nullif({{ denominator }}, 0)
{%- endmacro %}

{# A price with the tax on it. The rate is its own macro, so that a test can change it. #}
{% macro tax_rate() %}{{ return(0.1) }}{% endmacro %}

{% macro price_with_tax(amount) -%}
    ({{ amount }} * (1 + {{ tax_rate() }}))::numeric(16, 2)
{%- endmacro %}
