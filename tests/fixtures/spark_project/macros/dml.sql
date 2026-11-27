{# macros that run statements themselves (#30) #}

{% macro upsert_orders(target, source) %}
  {% do run_query("merge into " ~ target ~ " as t using " ~ source ~ " as s on t.id = s.id when matched then update set value = s.value when not matched then insert (id, value) values (s.id, s.value)") %}
{% endmacro %}

{% macro append_row(target) %}
  {% do run_query("insert into " ~ target ~ " values (9, 'new')") %}
{% endmacro %}

{% macro row_count(table) %}(select count(*) from {{ table }}){% endmacro %}
