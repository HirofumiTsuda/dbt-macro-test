{# A quantity must not be negative: the macro stops the run with an error when it is. #}
{% macro quantity(value) %}
    {% if value < 0 %}
        {{ exceptions.raise_compiler_error("quantity must not be negative, got " ~ value) }}
    {% endif %}
    {{ value }}
{% endmacro %}

{# A status whose name is going away: it gives the status, and says so with a warning. #}
{% macro status(value) %}
    {% if value == 'pending' %}
        {% do exceptions.warn("status 'pending' is deprecated, use 'open'") %}
    {% endif %}
    '{{ value }}'
{% endmacro %}
