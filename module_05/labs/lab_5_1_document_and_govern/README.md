# Lab 5.1: Document and Govern a dbt Project on Unity Catalog

A model that works is not yet a model people can find, trust or safely use. In this lab you take a
working but undocumented dbt project and make it **documented, discoverable, access-controlled,
traceable and auditable**, using dbt for what it is good at (logic, docs, a reviewable history) and
Unity Catalog for what it is good at (enforced permissions, runtime lineage, one place to look).

**Before you start:** complete the setup in the [module README](../../README.md) so that `dbt build`
runs green in your schema.

## What you will learn

- Generate the dbt docs site and measure how much of a project is documented.
- Enrich models with descriptions, **doc blocks**, `meta` and `tags`.
- Persist that documentation to Unity Catalog with `persist_docs`, so it is visible where data is queried.
- Apply Unity Catalog **tags**, **grants** and a **column mask** from dbt, and know which one to use when.
- Tell **dbt lineage** (logical) from **Unity Catalog lineage** (physical), and use both.
- Make a delivery reproducible and auditable: pinned dbt versions, saved artifacts, and tagged queries.

## What's in this folder

| File | Purpose |
|------|---------|
| `README.md` | This lab guide. |
| `solution/` | The reference answer: finished YAML, `docs.md` and `dbt_project.yml`. Peek only after you have tried. |

The **starter** is the module as shipped. The solution lives under `labs/`, outside `model-paths`, so
dbt ignores it until you copy files from it.

## The scenario

`dim_customers` holds names and email addresses. Before the Jaffle Shop analysts get access, the data
platform team needs: every column described, personal data tagged and masked, the right people able
to read the marts, and a way to prove later what ran and where the data came from.

## Lab steps

Run everything from the module root (`module_05/`) with your virtual environment active
(`dbt --version` should show dbt-databricks 1.11.7) and your environment exported:

```bash
set -a && source .env && set +a
```

dbt 1.11 prints several `WARNING`s about upcoming behavior changes. They are expected.

### 1. See what is documented today

```bash
dbt docs generate
python3 scripts/doc_coverage.py
```

`dbt docs generate` compiles the project and queries the warehouse for the columns that really exist,
writing `target/manifest.json` (what you wrote) and `target/catalog.json` (what is there). The script
compares them. The starter reports **0 of 39 columns documented**.

Now look at the site:

```bash
dbt docs serve
```

Open <http://localhost:8080> and open the lineage graph (the blue button, bottom right). Find the
**ephemeral** model `int_customer_orders` and the **exposure** `weekly_orders_dashboard` at the end of
the graph. Remember them for step 6.

### 2. Document the project

Add a description to every column. Two ways to write one:

```yaml
columns:
  - name: customer_id
    description: The customer's key. A UUID, unique per customer.        # inline
  - name: customer_id
    description: "{{ doc('customer_id') }}"                             # a reusable doc block
```

A **doc block** is written once in a `.md` file and reused wherever the column appears, so
`customer_id` is described identically in five models. Start with `stg_customers`, then compare with
the [solution](solution/models/staging/_staging.yml). To finish quickly, copy the solution files over
the starter:

```bash
S=labs/lab_5_1_document_and_govern/solution/models
cp $S/docs.md models/
cp $S/staging/_staging.yml models/staging/
cp $S/intermediate/_intermediate.yml models/intermediate/
cp $S/marts/_marts.yml models/marts/
```

`models/docs.md` also defines `{% docs __overview__ %}`, which replaces the landing page of the docs
site. Then check:

```bash
dbt docs generate
python3 scripts/doc_coverage.py        # 39/39 = 100%
```

> The solution `_marts.yml` also carries the settings for steps 4 and 5. That is fine with the pinned
> dbt-databricks 1.11.7: the tags are applied by your next build, the grants do nothing until you pass
> `reader_principal`, and the column mask is ignored until you turn on the flag in step 5. (Do not
> turn the flag on before step 5: the mask function does not exist until the hook is added there.)

### 3. Persist the documentation to Unity Catalog

So far the descriptions exist only on the dbt docs site. `persist_docs` writes them to Unity Catalog as
table and column **comments**, so they show up in Catalog Explorer, in `DESCRIBE`, and to every tool
and user that reads the table. In `dbt_project.yml`, add a `seeds:` block and add `+persist_docs` to the
`models: module_05:` block that is already there. The file must keep exactly **one** `models:` block:
a second one silently replaces the first, and every model then builds as a view.

```yaml
seeds:
  module_05:
    +persist_docs:
      relation: true

models:
  module_05:
    +persist_docs:
      relation: true
      columns: true
    staging:
      +materialized: view
    intermediate:
      +materialized: ephemeral
    marts:
      +materialized: table
```

Rebuild, then check Unity Catalog. Run `dbt compile`, then paste
`target/compiled/module_05/analyses/uc_documentation_check.sql` into the SQL editor, or look at
`dim_customers` in Catalog Explorer:

```bash
dbt build
dbt compile
```

Every table and view now has a table comment and a comment on every column. (The ephemeral
`int_customer_orders` is not in Unity Catalog, so it has neither.) The seeds get a table comment only
(they have no column descriptions), so their column counts stay 0 in the check.

### 4. Enrich with metadata and tags

dbt and Unity Catalog each have their own idea of a tag, and they do different jobs:

| | What it is | Where it lives | Use it for |
|---|---|---|---|
| `meta` | Free-form key/values | dbt docs site and `manifest.json` | owner, maturity, anything for dbt tooling |
| `tags` (dbt) | A label for selecting nodes | dbt only | `dbt build --select tag:pii` |
| `databricks_tags` | Key/values on the Unity Catalog object | Unity Catalog | discovery, search, policies, audits |

The solution `_marts.yml` sets all three. Look at `dim_customers`:

```yaml
config:
  meta: {owner: data-platform, contains_pii: true, maturity: production}
  tags: [pii]
  databricks_tags: {domain: sales, contains_pii: "true"}        # on the TABLE
columns:
  - name: customer_email
    databricks_tags: {data_classification: pii}                 # on the COLUMN
```

Try the selector, then check Unity Catalog: paste the compiled
`target/compiled/module_05/analyses/uc_tags_and_masks.sql` into the SQL editor. If you copied the
solution in step 2, your last build already applied the tags:

```bash
dbt ls --select tag:pii            # stg_customers and dim_customers
dbt compile                        # compiles the analyses to target/compiled/module_05/analyses/
```

> **Placement matters.** Table-level `databricks_tags` go under `config:`. Column-level
> `databricks_tags` (and `column_mask`, step 5) go **directly on the column**, not under its `config:`.
> Put them under `config:` and dbt builds green and silently applies nothing.
>
> With `column_mask` on a column, dbt 1.11 prints `CustomKeyInObjectDeprecation` ("this may mean the key
> is a typo"). That is dbt-core's schema check, which does not know this adapter key (it does know
> `databricks_tags`, so those never warn). dbt-databricks 1.11 reads `column_mask` from the column
> anyway, so the mask does apply. A future dbt-core could turn the warning into an error.

### 5. Control access

Unity Catalog enforces access. dbt declares it, and re-applies it on every build, so it cannot drift.

**5a. Grants.** Choose a group or user to give `SELECT` on the marts, then rebuild with it:

```bash
dbt build --select marts --vars '{"reader_principal": "<group-or-user>"}'
```

then run `SHOW GRANTS ON TABLE <catalog>.<schema>.fct_orders` in the SQL editor. The grant comes from
`grants: select:` in the YAML, driven by the `reader_principal` var. Now rebuild **without** the var:

```bash
dbt build --select marts
```

and `SHOW GRANTS` again. The `SELECT` is gone: with the var unset the grant list is empty, and **dbt
reconciles grants to match your YAML, so an empty list revokes.** Deleting the whole `grants:` block is
different: dbt then manages no grants for that model and leaves the existing `SELECT` in place. (The
grantee also needs `USE CATALOG` and `USE SCHEMA`, which dbt does not grant.)

**5b. A column mask.** Grants control who can read a table. A mask controls what a reader *sees* in a
column. Three pieces:

1. **The function** is the policy. [`macros/governance.sql`](../../macros/governance.sql) creates
   `mask_email` in your schema. People in the group named by `pii_reader_group` see the real email;
   everyone else sees `***@example.com`.
2. **A hook** creates the function before any model uses it, so one `dbt build` works. Add to
   `dbt_project.yml`:

   ```yaml
   on-run-start:
     - "{{ create_pii_mask_function() }}"
   ```

3. **The mask** attaches the function to the column (already in the solution `_marts.yml`):

   ```yaml
   - name: customer_email
     column_mask:
       function: "`{{ target.catalog }}`.`{{ target.schema }}`.mask_email"
   ```

dbt-databricks 1.11 applies masks only with the revamped materializations. Turn them on in
`dbt_project.yml`, then build:

```yaml
flags:
  use_materialization_v2: true
```

```bash
dbt build
```

dbt counts the `on-run-start` hook as a node, so a build of one model now reports one more pass than
before (`--select dim_customers` gives `PASS=2`).

Query the table. You are not in the default group (the lab assumes no group called `pii_readers`
exists in your account), so the email is masked:

```sql
select customer_name, customer_email from <catalog>.<schema>.dim_customers order by customer_name limit 3;
-- Alexandria Jarvis | ***@example.com
```

Now put yourself in the reader group. `account users` contains everyone in the account, so it works for
the demo (use a real, dedicated group outside a lab):

```bash
dbt build --select dim_customers --vars '{"pii_reader_group": "account users"}'
```

The same query now shows real addresses. Rebuild without the var (`dbt build --select dim_customers`)
and they are masked again: the mask stays attached to the column across rebuilds.

> **Without the flag, a `column_mask` is silently ignored:** the build is green and the email is
> readable. Always read the data back, as above, instead of trusting a green build.

### 6. Compare dbt lineage and Unity Catalog lineage

Two graphs, two different questions:

| | dbt lineage | Unity Catalog lineage |
|---|---|---|
| Question | What does the code say depends on what? | What actually read and wrote what? |
| Granularity | Table | Table and **column** |
| Sees | Ephemeral models, exposures, tests | Every query on Databricks: dbt, notebooks, dashboards, ad hoc |
| Misses | Anything outside dbt | Ephemeral models (no table), anything not yet run |
| Where | The docs site; `manifest.json` | Catalog Explorer, `system.access.*` |

Look at Unity Catalog's graph: open `fct_orders` in Catalog Explorer and select **Lineage**. Then
compare the two programmatically once your build has finished. System tables are not real-time and record
availability varies by table (see the [system tables reference](https://docs.databricks.com/aws/en/admin/system-tables/)), so if an edge is missing, re-run it:

```bash
python3 scripts/compare_lineage.py
```

Expect four groups. Every edge Unity Catalog recorded should match a dbt path once the ephemeral
model is bridged. That includes **`stg_orders → dim_customers`**: dbt's graph goes through the
ephemeral `int_customer_orders`, while Unity Catalog only ever saw the SQL that ran, so it records a
direct edge. The dbt-only edges are the ones touching the ephemeral model and the exposure. To list
every edge Unity Catalog recorded, paste the compiled `analyses/uc_lineage.sql`. For column lineage,
paste the compiled `analyses/uc_column_lineage.sql`: Unity Catalog traces `dim_customers.lifetime_spend`
back to the exact `stg_orders` columns it came from.

**Optional.** Make Unity Catalog report something dbt cannot know. Pretend an analyst builds their own
table from your mart, outside dbt:

```sql
create table <catalog>.<schema>.analyst_scratch as
select order_status, count(*) as orders from <catalog>.<schema>.fct_orders group by 1;
```

Run `compare_lineage.py` again (re-run it if the new edge is not there yet). `fct_orders → analyst_scratch` appears under
**Unity Catalog only**: a consumer your dbt project never declared. This is why the two are
*complementary*. Drop the table when you are done.

To query the system tables as a non-admin you need `USE CATALOG` on `system`, `USE SCHEMA` on
`system.access`, and `SELECT` on `system.access.table_lineage` and `system.access.column_lineage`.

### 7. Make it reproducible and auditable

You can reproduce a delivery if you can recreate the **code, the tools, the data and the settings**,
and audit it if you can later answer *who ran what, when, and with what result*.

| To prove | Evidence |
|---|---|
| The code | The git commit. dbt's docs, tests and lineage are all derived from it. |
| The tools | `requirements.txt` pins `dbt-core==1.11.8` and `dbt-databricks==1.11.7`. This module uses no dbt packages, so there is no package lock. |
| What ran | `target/run_results.json`, `manifest.json`, `catalog.json`: keep them per run. |
| Who and why | `query_tags` in `profiles.yml`, read back from `system.query.history`. |
| The data's history | Delta: `DESCRIBE HISTORY <catalog>.<schema>.fct_orders` |
| Docs have not rotted | `python3 scripts/doc_coverage.py --min 100` exits non-zero below 100%, so it can gate a CI job |

Your `profiles.yml` already carries `query_tags: '{"project": "module_05", "team": "analytics"}'`.
dbt-databricks adds its own tags to every query too (`@@dbt_model_name`, `@@dbt_materialized`,
versions). Rebuild, then run `analyses/query_audit.sql`. Query history records are typically available within an hour
([record availability](https://docs.databricks.com/aws/en/admin/system-tables/query-history)), so re-run it if it comes back empty. Every statement dbt
sent is attributable to a project, a team, a model and a user.

```bash
dbt docs generate
python3 scripts/doc_coverage.py --min 100 && echo "documentation gate passed"
```

The gate counts the tables and views in Unity Catalog. It fails below 100% of columns, when a model
has no description at all, and when a model is missing from `catalog.json` (not built, or `dbt docs generate`
was limited with `--select`). Ephemeral models are not counted, because they have no table to compare with.

## Check your work

| You should be able to show | How |
|---|---|
| Documentation coverage went 0% → 100% | Step 1 vs step 2: `doc_coverage.py` |
| The docs reached Unity Catalog | Step 3: `uc_documentation_check.sql`, or Catalog Explorer |
| Personal data is tagged | Step 4: `data_classification = pii` on two columns in `uc_tags_and_masks.sql` |
| Access is enforced, not just declared | Step 5: `SHOW GRANTS`, and a masked email you can unmask by changing the group |
| You can explain the two lineage graphs | Step 6: the output of `compare_lineage.py` |
| A delivery you could audit | Step 7: tagged queries in `query_audit.sql` |

## Gotchas

- **Green does not mean applied.** A column mask without the flag, or tags under the wrong key, build
  green and do nothing. Read the data back from Unity Catalog.
- **dbt owns the comments.** Every build rewrites table and column comments from your YAML, so a
  comment someone types into Catalog Explorer is overwritten by the next `dbt build`. Change the YAML.
- **Tags are not removed by deleting them from YAML.** dbt applies tags but does not unset the ones you
  stop listing. Remove stale tags yourself (`ALTER TABLE ... UNSET TAGS`). Grants are different: dbt
  *does* revoke them.
- **A mask is not a grant, and it covers one column of one table.** A user with `SELECT` still reads the table; the mask changes what they see in `dim_customers.customer_email`. The raw address is still in the `customers` seed and the `stg_customers` view, so in a real project restrict who can read raw and staging schemas with grants too.
- **Lineage is runtime.** Unity Catalog records what ran, so a model you have not built has no lineage.
  Column lineage needs tables referenced by name, not by path.
- **System tables are not real-time.** Record availability varies by table (query history is typically
  available within an hour), so re-run a lineage or audit query before concluding a record is missing.
- **Ephemeral models never reach Unity Catalog.** They are in the dbt graph and in no table, comment
  or lineage edge. Document them in dbt, and know that Unity Catalog will not show them.
