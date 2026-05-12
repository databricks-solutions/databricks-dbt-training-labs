{# A macro to convert cents to dollars with consistent formatting #}

{% macro cents_to_dollars(column_name) -%}
    {{ return(adapter.dispatch('cents_to_dollars')(column_name)) }}
{%- endmacro %}

{% macro default__cents_to_dollars(column_name) -%}
    ({{ column_name }} / 100)::numeric(16, 2)
{%- endmacro %}

{% macro databricks__cents_to_dollars(column_name) -%}
    CAST({{ column_name }} / 100.0 AS DECIMAL(16, 2))
{%- endmacro %}
