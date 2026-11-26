{% macro hello(name) %}Hello, {{ name }}!{% endmacro %}

{% macro with_quotes() %}it's a 'quoted' word{% endmacro %}

{% macro padded() %}

    indented text

{% endmacro %}

{% macro upsert_sql(target, source, key) %}
merge into {{ target }} as t
using {{ source }} as s
on t.{{ key }} = s.{{ key }}
when matched then update set t.value = s.value
when not matched then insert ({{ key }}, value) values (s.{{ key }}, s.value)
{% endmacro %}
