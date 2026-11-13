-- Is the documentation in Unity Catalog? One row per table: how many columns have a comment.
-- Run `dbt compile`, then paste target/compiled/module_05/analyses/uc_documentation_check.sql into the
-- SQL editor. Before persist_docs, every count is 0; after it, the models match the dbt docs site.
-- The seeds get a table comment only (they have no column descriptions), so their column count stays 0.

select

    t.table_name,
    t.table_type,
    t.comment is not null as has_table_comment,
    count(c.column_name) as columns,
    count(c.comment) as columns_with_comment

from {{ target.catalog }}.information_schema.tables as t

inner join {{ target.catalog }}.information_schema.columns as c
    on t.table_schema = c.table_schema
    and t.table_name = c.table_name

where t.table_schema = lower('{{ target.schema }}')

group by t.table_name, t.table_type, t.comment

order by t.table_name
