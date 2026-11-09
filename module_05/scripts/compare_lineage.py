#!/usr/bin/env python3
"""Compare dbt's logical lineage with Unity Catalog's physical lineage for this project.

dbt lineage is what the code SAYS depends on what (target/manifest.json, written by any dbt command).
Unity Catalog lineage is what the queries that ACTUALLY RAN read and wrote (system.access.table_lineage).
They agree on most edges and, usefully, disagree on a few:

  dbt only   ephemeral models and exposures (they have no table to record), or a model that has not
             been built yet
  UC only    readers and writers dbt does not know about: a dashboard, a notebook, an ad-hoc query

Needs the same environment variables as dbt (source your .env) and SELECT on system.access.table_lineage.
System tables are not real-time (record availability varies by table), so re-run if an edge is missing.
Edges with no source table (for example a seed load) are not edges between tables, so they are left
out of the comparison.

    python3 scripts/compare_lineage.py [--days 7]
"""

import argparse
import json
import os
import sys
from pathlib import Path

from databricks import sql

MANIFEST = Path(__file__).resolve().parent.parent / "target" / "manifest.json"


def rel(node):
    """catalog.schema.name of a built node, lower-cased, or None (ephemeral models are never built)."""
    name = node.get("relation_name")
    return name.replace("`", "").lower() if name else None


def dbt_edges(manifest):
    """Return (raw, physical). raw = every dbt edge, ephemeral models and exposures included.
    physical = what Unity Catalog can see: ephemeral models are bridged, so a -> eph -> b becomes a -> b."""
    nodes = {**manifest["nodes"], **manifest["sources"], **manifest.get("exposures", {})}
    label = {}
    for uid, n in nodes.items():
        if n["resource_type"] in ("model", "seed"):
            label[uid] = rel(n) or f"{n['name']} (ephemeral)"
        elif n["resource_type"] == "exposure":
            label[uid] = f"{n['name']} (exposure)"

    raw = {(label[p], label[c]) for c, ps in manifest["parent_map"].items() if c in label
           for p in ps if p in label}

    def built_parents(uid):
        for p in manifest["parent_map"].get(uid, []):
            if p not in label:
                continue
            if "(ephemeral)" in label[p]:
                yield from built_parents(p)
            else:
                yield p

    physical = {(label[p], label[c]) for c in label if "(" not in label[c]
                for p in built_parents(c)}
    return raw, physical


def uc_edges(days):
    # Match catalog and schema by equality: in a LIKE pattern the "_" in a name like module_05 is a wildcard.
    catalog, schema = os.environ["DATABRICKS_CATALOG"].lower(), os.environ["DATABRICKS_SCHEMA"].lower()
    with sql.connect(
        server_hostname=os.environ["DATABRICKS_HOST"].replace("https://", ""),
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=os.environ["DATABRICKS_TOKEN"],
    ) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select distinct lower(source_table_full_name), lower(target_table_full_name)
            from system.access.table_lineage
            where event_date >= date_sub(current_date(), ?)
              and (
                (lower(target_table_catalog) = ? and lower(target_table_schema) = ?)
                or (lower(source_table_catalog) = ? and lower(source_table_schema) = ?)
              )
            """,
            [days, catalog, schema, catalog, schema],
        )
        return {(s, t) for s, t in cur.fetchall() if s and t}


def short(name):
    return name.split(".")[-1] if "." in name and "(" not in name else name


def show(title, edges):
    print(f"\n{title} ({len(edges)})")
    for s, t in sorted(edges):
        print(f"  {short(s)}  ->  {short(t)}")
    if not edges:
        print("  (none)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--days", type=int, default=7, help="how far back to read Unity Catalog lineage")
    args = ap.parse_args()
    if not MANIFEST.exists():
        sys.exit("target/manifest.json not found. Run a dbt command first (e.g. `dbt build`).")
    missing = [v for v in ("DATABRICKS_HOST", "DATABRICKS_HTTP_PATH", "DATABRICKS_TOKEN",
                           "DATABRICKS_CATALOG", "DATABRICKS_SCHEMA") if v not in os.environ]
    if missing:
        sys.exit(f"missing environment variables: {', '.join(missing)}. Run `set -a && source .env && set +a`.")

    raw, physical = dbt_edges(json.loads(MANIFEST.read_text()))
    here = f"{os.environ['DATABRICKS_CATALOG']}.{os.environ['DATABRICKS_SCHEMA']}.".lower()
    if not any(name.startswith(here) for edge in physical for name in edge):
        print(f"warning: target/manifest.json has no models in {here}* - it was built for another schema or "
              "catalog, so every edge below will look like a mismatch. Run `dbt compile` with this .env.\n",
              file=sys.stderr)
    uc = uc_edges(args.days)
    # Edges that touch an ephemeral model or an exposure can never be in Unity Catalog, by construction.
    logical_only = {e for e in raw if any("(" in x for x in e)}

    print(f"dbt edges: {len(raw)}   Unity Catalog edges: {len(uc)}")
    show("In both", physical & uc)
    show("dbt only, expected: touches an ephemeral model or an exposure", logical_only)
    show("dbt only, NOT expected: built-model edge Unity Catalog has not seen (not built yet, or not recorded yet)",
         physical - uc)
    show("Unity Catalog only: something other than this dbt project reads or writes here", uc - physical)


if __name__ == "__main__":
    main()
