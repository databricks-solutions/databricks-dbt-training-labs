{#
    Governance helpers for Lab 5.1. Nothing here runs until the lab wires it in.

    create_pii_mask_function()
        Creates the Unity Catalog SQL function that masks an email address, in YOUR dev schema. The
        function is the policy; the column mask in dim_customers' YAML attaches it to a column.
        Members of the group named by the `pii_reader_group` var see the real value; everyone else
        sees ***@<domain> (just ***@ if the value has no '@', rather than an error; a NULL stays NULL). The default group does not exist, so by default everyone sees the masked
        value, which is the safe failure mode. Lab 5.1 shows how to flip it.

    Wire it in with an on-run-start hook (see the lab guide), so a single `dbt build` creates the
    function BEFORE any model that references it.
#}

{% macro create_pii_mask_function() %}

    {%- set fn = '`' ~ target.catalog ~ '`.`' ~ target.schema ~ '`.mask_email' -%}
    {%- set group = var('pii_reader_group', 'pii_readers') | replace("'", "''") -%}

    create or replace function {{ fn }}(email string)
    returns string
    comment 'Masks the local part of an email address unless the caller is in the pii reader group.'
    return case
        when email is null then null
        when is_account_group_member('{{ group }}') then email
        else concat('***@', coalesce(try_element_at(split(email, '@'), 2), ''))
    end

{% endmacro %}
