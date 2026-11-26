{# The code of an order: a prefix and the number, to six digits. It returns text, not SQL. #}
{% macro order_code(prefix, number) %}
    {{ return(prefix ~ '-' ~ ('%06d' | format(number))) }}
{% endmacro %}

{# A name as it goes in an address: lower case, letters and digits, joined by dashes. #}
{% macro slug(name) %}
    {{ return(modules.re.sub('[^a-z0-9]+', '-', name | lower) | trim('-')) }}
{% endmacro %}
