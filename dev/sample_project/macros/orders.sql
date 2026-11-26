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

{# Writes, with a `statement` block instead of `run_query`: copies the cancelled orders of one
   relation into another. #}
{% macro archive_cancelled(orders, archive) %}
    {% call statement('archive_cancelled', fetch_result=False, auto_begin=False) %}
        insert into {{ archive }} select * from {{ orders }} where status = 'cancelled'
    {% endcall %}
{% endmacro %}

{# Reads, through `adapter`: the names of the columns of a relation, as one string. #}
{% macro order_columns(orders) -%}
    {{ adapter.get_columns_in_relation(orders) | map(attribute='name') | join(',') }}
{%- endmacro %}
