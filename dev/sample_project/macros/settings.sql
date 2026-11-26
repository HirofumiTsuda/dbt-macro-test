{# A greeting for the country of the project (a var) and the shop of the environment (a variable). #}
{% macro greeting(name) %}
    'Hello, {{ name }}! ({{ var("country") }}, {{ env_var("SHOP_NAME", "main shop") }})'
{% endmacro %}
