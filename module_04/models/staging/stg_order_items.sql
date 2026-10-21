{#
    Staging order items: one row per item on an order, straight from the seed.

    Defect D07 (two lines whose product_id is not in products) passes through untouched.
#}

select

    order_item_id,
    order_id,
    product_id

from {{ ref('order_items') }}
