-- Column-level lineage for one column: where does dim_customers.lifetime_spend come from?
-- Change the target table and column to trace any other column. Unity Catalog resolves this through
-- views and through the inlined (ephemeral) model; the dbt docs graph is table-level only.

select distinct

    source_table_name,
    source_column_name,
    target_table_name,
    target_column_name

from system.access.column_lineage

where event_date >= date_sub(current_date(), 7)
    and target_table_full_name = lower('{{ target.catalog }}.{{ target.schema }}.dim_customers')
    and target_column_name = 'lifetime_spend'

order by source_table_name, source_column_name
