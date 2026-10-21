{#
    Staging customers: one row per customer, straight from the seed.

    Defects D01 (NULL customer_name) and D02 (duplicated customer_id) pass through untouched --
    surfacing them is the job of the tests you add, not of this model.
#}

select

    customer_id,
    customer_name

from {{ ref('customers') }}
