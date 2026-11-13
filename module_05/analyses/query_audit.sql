-- Who ran which dbt queries, tagged with what? Shows YOUR queries from the last 7 days; delete the
-- executed_by line to see everyone's (needs permission to read the whole table).
-- Query history records are typically available within an hour, so re-run if it is empty.
-- Reads the query tags set in profiles.yml (query_tags) plus the tags dbt-databricks always adds
-- (@@dbt_model_name, @@dbt_materialized, versions).

select

    start_time,
    executed_by,
    query_tags['project'] as project,
    query_tags['team'] as team,
    query_tags['@@dbt_model_name'] as dbt_model,
    query_tags['@@dbt_materialized'] as materialization,
    execution_status

from system.query.history

where start_time >= current_timestamp() - interval 7 days
    and query_tags['project'] = 'module_05'
    and executed_by = current_user()

order by start_time desc

limit 50
