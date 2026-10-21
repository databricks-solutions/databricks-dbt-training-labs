{#
    Staging orders: one row per order, straight from the seed.

    Defects D03 (orphan customer_id), D04 (invalid order_status), D05 (negative tax_paid) and D06
    (subtotal != sum of item prices) pass through untouched -- surfacing them is the job of the
    tests you add, not of this model.

    The ONE switch in this model is for Lab 4.3's "make it pass" step. With

        --vars '{"quarantine_subtotal_defects": true}'

    the four D06 orders listed in defect_catalog are excluded. Because this model is a view, the var
    is applied when the VIEW IS BUILT, not when a test runs -- so rebuild the view with the var first,
    then run the test:

        dbt run --select stg_orders --vars '{"quarantine_subtotal_defects": true}'
        dbt test --select assert_order_subtotal_matches_items
#}

select

    order_id,
    customer_id,
    location_id,
    order_date,
    order_status,
    subtotal,
    tax_paid,
    order_total

from {{ ref('orders') }}

{% if var('quarantine_subtotal_defects', false) %}
where order_id not in (
    select row_key
    from {{ ref('defect_catalog') }}
    where defect_id = 'D06'
)
{% endif %}
