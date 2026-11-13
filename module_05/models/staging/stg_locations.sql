{# Staging locations: one row per store, straight from the seed. #}

select

    location_id,
    location_name,
    opened_at,
    tax_rate

from {{ ref('locations') }}
