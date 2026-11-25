{% macro pick(relation, columns) %}
    select {{ columns | join(', ') }}
    from {{ relation }}
{% endmacro %}
{% macro union_two(a, b) %}
select * from {{ a }}
union all
select * from {{ b }}
{% endmacro %}
{% macro commented() %}
with t as (select 1 as n, 'one' as name)
select * from t
-- the output ends with a line comment
{% endmacro %}
