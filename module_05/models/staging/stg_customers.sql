{#
    Staging customers: one row per customer, straight from the seed.

    customer_name and customer_email are personal data (PII). They are the columns Lab 5.1 tags
    and masks in Unity Catalog.
#}

select

    customer_id,
    customer_name,
    customer_email

from {{ ref('customers') }}
