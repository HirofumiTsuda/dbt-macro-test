{#
  Written into every generated project that has relations to drop (project/generate.py), and run by
  the tool after the tests, with the relations that the models logged as they made them:

      dbt run-operation _dmt_drop --args '{"relations": [{"database": ..., "schema": ...,
                                                         "identifier": ..., "type": ...}]}'

  drop_relation_if_exists is dbt's, dispatched by adapter, so there is nothing here for any one
  adapter. It does nothing for a relation that is already gone, which a temporary relation is on
  the adapters that drop it with the connection. The commit is needed: without it the drop is
  rolled back when dbt closes the connection.
#}
{% macro _dmt_drop(relations) %}
  {% for r in relations %}
    {% do drop_relation_if_exists(api.Relation.create(
        database=r['database'], schema=r['schema'], identifier=r['identifier'], type=r['type'])) %}
  {% endfor %}
  {% do adapter.commit() %}
{% endmacro %}
