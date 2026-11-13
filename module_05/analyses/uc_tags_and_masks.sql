-- Which Unity Catalog governance metadata did dbt apply? One row per tag or mask.
-- kind is table_tag, column_tag or column_mask. Empty before the Lab 5.1 governance step.

select 'table_tag' as kind, table_name as object_name, cast(null as string) as column_name,
       tag_name as name, tag_value as value
from {{ target.catalog }}.information_schema.table_tags
where schema_name = lower('{{ target.schema }}')

union all

select 'column_tag', table_name, column_name, tag_name, tag_value
from {{ target.catalog }}.information_schema.column_tags
where schema_name = lower('{{ target.schema }}')

union all

select 'column_mask', table_name, column_name, 'mask_function', mask_name
from {{ target.catalog }}.information_schema.column_masks
where table_schema = lower('{{ target.schema }}')

order by object_name, column_name, kind, name
