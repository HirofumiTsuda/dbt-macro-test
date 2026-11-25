{% macro is_running_in_ci() %}{{ return(false) }}{% endmacro %}
{% macro schema_for(name) %}'{{ ("pr_" ~ name) if is_running_in_ci() else name }}|{{ var("region") }}|{{ env_var("STAGE", "dev") }}'{% endmacro %}
