{# Staging order items: one row per item on an order, straight from the seed. #}

select

    order_item_id,
    order_id,
    product_id

from {{ ref('order_items') }}
