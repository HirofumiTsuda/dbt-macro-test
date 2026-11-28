{# Is dbt run by CI? (the environment variable CI is `true`) #}
{% macro is_running_in_ci() %}
    {{ return(env_var("CI", "false") == "true") }}
{% endmacro %}

{# The override of dbt's own macro: the schema a model goes to. Its own schema in the base schema's
   name in development, a schema of the CI run's own in CI, the base schema for a model with none. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set base = var("base_schema", "analytics") -%}
    {%- if custom_schema_name is none -%}
        {{ base }}
    {%- elif is_running_in_ci() -%}
        ci_{{ custom_schema_name | trim }}
    {%- else -%}
        {{ base }}_{{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
