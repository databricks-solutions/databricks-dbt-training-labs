{#
    Doc blocks: write a description once, reuse it everywhere with {{ doc('name') }}.

    dbt renders them into the docs site, and with persist_docs they are also written to Unity Catalog
    as table and column comments. Keep each block short: Catalog Explorer shows it as plain text.
#}

{% docs __overview__ %}

# Jaffle Shop: documentation and governance (Module 5)

A small coffee-and-jaffle shop, modelled in layers:

| Layer | Models | Materialized as |
|-------|--------|-----------------|
| Staging | `stg_*` | views |
| Intermediate | `int_customer_orders` | ephemeral (never exists in Unity Catalog) |
| Marts | `dim_customers`, `fct_orders` | Delta tables |

**Governance.** `dim_customers` holds personal data (name and email). Both columns are tagged
`data_classification = pii` in Unity Catalog, and the email is masked for everyone outside the PII
reader group. `fct_orders` holds no personal data.

**Lineage.** The graph on this site is dbt's *logical* lineage. For the *physical* lineage of what
actually ran, use the Lineage tab in Catalog Explorer.

{% enddocs %}

{% docs customer_id %}
The customer's key. A UUID, unique per customer.
{% enddocs %}

{% docs order_id %}
The order's key. A UUID, unique per order.
{% enddocs %}

{% docs order_status %}
Where the order is in its life: `placed`, `shipped`, `delivered`, `returned` or `cancelled`.
{% enddocs %}

{% docs pii_notice %}
Personal data. Tagged `data_classification = pii` in Unity Catalog. Do not copy it out of the governed schema.
{% enddocs %}

{#
    Staging columns are NOT tagged in Unity Catalog (only the dim_customers columns are), so they get a
    block that makes no claim about tags. persist_docs writes this text into the column comment, so a
    description must only say what is true of that column.
#}
{% docs pii_notice_staging %}
Personal data. Do not copy it out of the governed schema.
{% enddocs %}
