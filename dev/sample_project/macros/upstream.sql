{# Reads a model of the project, as a SQL expression: how many orders have a status. #}
{% macro orders_with_status(status) -%}
    (select count(*) from {{ ref('orders') }} where status = {{ status }})
{%- endmacro %}

{# Reads a source: what has been paid, as a SQL expression. #}
{% macro paid_total() -%}
    (select coalesce(sum(amount), 0) from {{ source('shop', 'payments') }} where status = 'paid')
{%- endmacro %}
