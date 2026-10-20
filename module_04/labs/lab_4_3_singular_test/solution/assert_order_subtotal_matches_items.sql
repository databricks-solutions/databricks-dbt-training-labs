-- LAB 4.3 SOLUTION: singular SQL test.
--
-- Rule: an order's subtotal must equal the sum of the list prices of its items.
-- A singular test returns the VIOLATING rows; zero rows means the test passes.
--
-- To use it, copy this file over the starter:
--   cp labs/lab_4_3_singular_test/solution/assert_order_subtotal_matches_items.sql \
--      data-tests/assert_order_subtotal_matches_items.sql

with

item_totals as (

    select
        order_items.order_id,
        sum(products.product_price) as items_subtotal

    from {{ ref('stg_order_items') }} as order_items

    -- Inner join: a line whose SKU is unknown (defect D07) has no price to add, so it adds nothing
    -- to the total. That keeps this test about ONE rule (subtotal vs items), not about D07.
    inner join {{ ref('stg_products') }} as products
        on order_items.product_id = products.product_id

    group by 1

)

select

    orders.order_id,
    orders.subtotal,
    coalesce(item_totals.items_subtotal, 0) as items_subtotal,
    orders.subtotal - coalesce(item_totals.items_subtotal, 0) as difference

from {{ ref('stg_orders') }} as orders

-- Left join + coalesce: an order with NO items has no row in item_totals, so its items_subtotal is
-- NULL. Without the coalesce, `subtotal <> NULL` evaluates to NULL (not true) and the WHERE clause
-- silently drops the row -- which would also hide an item-less order that claims a NON-ZERO subtotal.
-- With it, an item-less order compares its subtotal to 0: a legitimate subtotal of 0 passes, and a
-- bogus non-zero subtotal is correctly flagged.
left join item_totals
    on orders.order_id = item_totals.order_id

where orders.subtotal <> coalesce(item_totals.items_subtotal, 0)
