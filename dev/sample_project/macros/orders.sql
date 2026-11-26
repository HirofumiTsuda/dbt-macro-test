{# Writes: an upsert of the rows of one relation into another. It is given both. #}
{% macro upsert_orders(target, source) %}
    {% do run_query(
        "merge into " ~ target ~ " as t using " ~ source ~ " as s on t.id = s.id "
        ~ "when matched then update set status = s.status "
        ~ "when not matched then insert (id, status) values (s.id, s.status)"
    ) %}
{% endmacro %}

{# Writes: deletes the cancelled orders of a relation. #}
{% macro remove_cancelled(orders) %}
    {% do run_query("delete from " ~ orders ~ " where status = 'cancelled'") %}
{% endmacro %}

{# Reads: the total of the amounts of a relation, as a SQL expression. #}
{% macro order_total(orders) -%}
    (select sum(amount) from {{ orders }})
{%- endmacro %}
