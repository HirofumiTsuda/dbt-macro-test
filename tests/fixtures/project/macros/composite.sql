{% macro composite_columns() %}[1, 2, 3] as l, {'a': 1, 'b': 'x'} as s, map {'k1': 1, 'k2': 2} as m{% endmacro %}
{% macro numbers() %}
select * from (values (1, 'one'), (2, 'two')) as t(n, name)
{% endmacro %}
