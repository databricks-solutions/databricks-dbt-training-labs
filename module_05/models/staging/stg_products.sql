{# Staging products: one row per SKU, straight from the seed. #}

select

    product_id,
    product_name,
    product_type,
    product_price

from {{ ref('products') }}
