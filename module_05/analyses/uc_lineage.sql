-- Unity Catalog's PHYSICAL lineage for this schema: which tables were actually read to write which.
-- Compare with the dbt docs graph (LOGICAL lineage). Differences are the point: ephemeral models
-- and exposures exist only in dbt; readers outside dbt exist only here.
-- System tables are populated a few minutes after a query runs. A NULL source is a file load (a seed).

select distinct

    source_table_name,
    target_table_name

from system.access.table_lineage

where event_date >= date_sub(current_date(), 7)
    and (
        (target_table_catalog = lower('{{ target.catalog }}') and target_table_schema = lower('{{ target.schema }}'))
        or (source_table_catalog = lower('{{ target.catalog }}') and source_table_schema = lower('{{ target.schema }}'))
    )

order by target_table_name, source_table_name
