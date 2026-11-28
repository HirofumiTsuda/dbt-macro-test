{# Is dbt run by CI? (the environment variable CI is `true`) #}
{% macro is_running_in_ci() %}
    {{ return(env_var("CI", "false") == "true") }}
{% endmacro %}

{# The override of dbt's own macro: the schema a model goes to. The base schema (the var, else the
   schema of the target) for a model with none of its own, the base schema's name with its own behind
   it in development, a schema of the CI run's own in CI. dbt calls it for every model, those that the
   tool generates too: a name written in it would take them all there. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set base = var("base_schema", target.schema) -%}
    {%- if custom_schema_name is none -%}
        {{ base }}
    {%- elif is_running_in_ci() -%}
        ci_{{ custom_schema_name | trim }}
    {%- else -%}
        {{ base }}_{{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
