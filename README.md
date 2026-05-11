# databricks-dbt-training-labs

Self-service, hands-on labs that complement an upcoming [dbt](https://www.getdbt.com/) on [Databricks](https://www.databricks.com/) course. The labs let you work through the course material at your own pace in your own workspace, taking you from a clean dbt project to production-grade models on Unity Catalog with optional deployment via [Declarative Automation Bundles (DABs)](https://docs.databricks.com/dev-tools/bundles) and Lakeflow Jobs.

## Mission

- **Course companion.** Each lab maps to a section of the dbt-on-Databricks course and is designed to be opened, read, and run end-to-end without an instructor.
- **Self-service.** Clone the repo, fill in your own workspace values locally, and run. No shared environment, no shared state.
- **Production-shaped, not toy.** Models follow the staging + marts layering, use Unity Catalog with `dbt-databricks`, and are deployable as Lakeflow Jobs via DABs.
- **Public-safe.** Everything tracked here is portable across any Databricks workspace; workspace-specific config stays local (see [`local_deployment/`](local_deployment/)).

## What's inside

The first lab is the canonical [Jaffle Shop](https://github.com/dbt-labs/jaffle-shop-classic) dataset, modelled end-to-end with `dbt-databricks` against a SQL Warehouse. It is intentionally a **first step**: a small, well-known schema that lets you focus on getting the local dev loop, profiles, seeds, sources, staging/marts layering, tests, packages, and DAB deployment working before tackling harder modelling problems.

Future labs will build on this foundation with **several deeper and more diverse examples of data modelling in Databricks**, planned to cover patterns such as:

- Slowly Changing Dimensions (Type 1 / 2) using dbt snapshots
- Incremental models with merge / append / insert-overwrite strategies on Delta
- Streaming sources and CDC ingestion patterns (DLT / Lakeflow + dbt)
- Star and dimensional modelling beyond the Jaffle toy schema
- Data Vault style raw / business vault layers
- Wide event / semi-structured (JSON, variants) modelling
- Performance tuning: liquid clustering, partitioning, Z-ORDER, photon, materialization choice
- Unity Catalog governance: row/column masking, tags, lineage-aware models
- Multi-environment promotion (dev / staging / prod) via DAB targets and CI

Each subsequent lab lands as its own top-level project folder, mirroring the `jaffle_shop/` layout, so you can run them independently in the same workspace.

| Path | Purpose |
|------|---------|
| [`jaffle_shop/`](jaffle_shop/) | Lab 01 — the dbt project: staging + marts models, seeds, macros, tests, packages. |
| [`local_deployment/`](local_deployment/) | Workspace-specific DAB and deploy config. Only the README is tracked; everything else stays local. |
| [`.cursor/rules/`](.cursor/rules/) | Cursor agent guardrails: public-repo compliance, branch conventions, coding standards. |

## Prerequisites

- A Databricks workspace with Unity Catalog enabled
- A SQL Warehouse (Serverless or Classic)
- A catalog and schema you own (or the right to create one)
- [Databricks CLI](https://docs.databricks.com/dev-tools/cli/install.html) v0.218+ configured with a profile
- Python 3.10+
- `dbt-databricks>=1.8.0,<2.0.0`

## Quick start (local dbt run)

```bash
cd jaffle_shop

# 1. Copy the templates -- both copies are gitignored.
cp .env.template .env
cp profiles.yml.example profiles.yml

# 2. Open .env in your editor and fill in REAL values for every variable:
#      DATABRICKS_HOST          -> https://<your-workspace>.cloud.databricks.com
#      DATABRICKS_HTTP_PATH     -> /sql/1.0/warehouses/<your-warehouse-id>
#      DATABRICKS_CATALOG       -> <your-catalog>
#      DATABRICKS_SCHEMA        -> jaffle_shop  (or any schema you own)
#      DATABRICKS_TOKEN         -> <your-pat>   (or use OAuth, see below)
#    profiles.yml reads these via env_var() at runtime, so you only fill in .env.

# 3. Install dbt and run.
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

set -a && source .env && set +a       # export the env vars to dbt
dbt deps
dbt debug                             # confirms connection before you run anything
dbt seed --full-refresh --vars '{"load_source_data": true}'
dbt run
dbt test
```

`profiles.yml` and `.env` are gitignored. Never commit them.

## Optional: deploy as a Lakeflow Job via DAB

The DAB bundle (`databricks.yml` at the repo root) is workspace-specific and therefore gitignored. See [local_deployment/README.md](local_deployment/README.md) for a placeholder bundle you can copy and fill in for your environment.

### Authenticate the CLI

`databricks bundle …` needs a CLI profile that points at the same workspace you're deploying to. The recommended approach is a [service principal](https://docs.databricks.com/dev-tools/auth.html#service-principal-oauth) with an OAuth client_id / client_secret -- no PATs, no expiring tokens. Add a profile to `~/.databrickscfg`:

```ini
[dbt-ws-profile]
host          = https://<your-workspace>.cloud.databricks.com
client_id     = <service-principal-client-id>
client_secret = <service-principal-oauth-secret>
```

If you'd rather use a PAT for a quick test, replace the OAuth pair with `token = <your-pat>`.

### Validate, deploy, run

From the repo root, pass `--profile` to every bundle command (or set `DATABRICKS_CONFIG_PROFILE=dbt-ws-profile` once for the shell):

```bash
databricks bundle validate --profile=dbt-ws-profile
databricks bundle deploy   --profile=dbt-ws-profile
databricks bundle run jaffle_shop_dbt_job --profile=dbt-ws-profile
```

## How to get help

Databricks does not offer official support for this content. For questions or bugs, please open a GitHub issue and the team will help on a best-effort basis.

## Security

Please report security issues per [SECURITY.md](SECURITY.md).

## License

See [LICENSE.md](LICENSE.md) and [NOTICE.md](NOTICE.md). All third-party packages used by this lab are listed in `jaffle_shop/packages.yml` and `jaffle_shop/requirements.txt`; refer to each project's own license.
