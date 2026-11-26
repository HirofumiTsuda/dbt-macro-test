{#
  Written into every generated project that has relations to drop (project/generate.py), and run by
  the tool after the tests, with the relations that the models logged as they made them:

      dbt run-operation _dmt_drop --args '{"relations": [{"database": ..., "schema": ...,
                                                         "identifier": ..., "type": ...}]}'

  get_drop_sql is dbt's, dispatched by adapter, and its statement says `if exists`, so there is
  nothing here for any one adapter and a relation that is already gone (a temporary relation is, on
  the adapters that drop it with the connection) is not an error. The statement is run with
  auto_begin=True, in a transaction, and then committed: without the commit duckdb rolls the drop
  back when dbt closes the connection, and without the transaction Postgres, whose drop opens none,
  fails the commit ("Tried to commit transaction ..., but it does not have one open").
#}
{% macro _dmt_drop(relations) %}
  {% for r in relations %}
    {% set relation = api.Relation.create(
        database=r['database'], schema=r['schema'], identifier=r['identifier'], type=r['type']) %}
    {% call statement('_dmt_drop', auto_begin=True) %}{{ get_drop_sql(relation) }}{% endcall %}
  {% endfor %}
  {% do adapter.commit() %}
{% endmacro %}
