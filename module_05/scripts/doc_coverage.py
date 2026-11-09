#!/usr/bin/env python3
"""Report how much of the project is documented, from dbt's own artifacts.

Run `dbt docs generate` first: it writes target/catalog.json (the columns that REALLY exist in the
warehouse) next to target/manifest.json (the descriptions you wrote). Comparing the two is the only
way to catch a column that exists in Unity Catalog but has no description in dbt.

    python3 scripts/doc_coverage.py                  # print the table
    python3 scripts/doc_coverage.py --min 100        # exit 1 if coverage < 100% (a CI gate)

Only models that exist in the warehouse are counted: this project's tables and views, not seeds, tests,
package models or ephemeral models (an ephemeral model has no table, so it has no catalog entry and
its columns cannot be checked against what really exists). With --min the gate also fails when a
built model has no model-level description, or is missing from catalog.json altogether (it was not
built, or `dbt docs generate` was limited with --select), so it cannot pass by skipping a model.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

TARGET = Path(__file__).resolve().parent.parent / "target"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--min", type=float, default=None, help="fail (exit 1) below this %% of columns")
    args = ap.parse_args()

    try:
        manifest = json.loads((TARGET / "manifest.json").read_text())
        catalog = json.loads((TARGET / "catalog.json").read_text())
    except FileNotFoundError as e:
        sys.exit(f"{e.filename} not found. Run `dbt docs generate` first.")

    # `dbt docs generate` writes both files together. A manifest much newer than the catalog means the
    # catalog is stale (a later dbt command rewrote the manifest), so the column list may be out of date.
    gen = {k: datetime.fromisoformat(v["metadata"]["generated_at"].replace("Z", "+00:00"))
           for k, v in (("manifest", manifest), ("catalog", catalog))}
    if gen["manifest"] - gen["catalog"] > timedelta(minutes=5):
        print("warning: catalog.json is older than manifest.json. Run `dbt docs generate` for fresh numbers.",
              file=sys.stderr)

    rows, total, documented, undescribed, not_in_catalog = [], 0, 0, [], []
    for uid, node in sorted(manifest["nodes"].items()):
        if node["resource_type"] != "model" or node["package_name"] != manifest["metadata"]["project_name"]:
            continue
        built = catalog["nodes"].get(uid)
        if built is None:
            # An ephemeral model never exists in the warehouse, so it has no catalog entry by design.
            # Anything else missing from the catalog was not built: remember it so the gate can fail.
            if node["config"].get("materialized") != "ephemeral":
                not_in_catalog.append(node["name"])
            continue
        cols = list(built["columns"])
        yml = {k.lower(): v for k, v in node["columns"].items()}  # Unity Catalog names are lower case
        described = [c for c in cols if (yml.get(c.lower(), {}).get("description") or "").strip()]
        has_desc = bool((node.get("description") or "").strip())
        if not has_desc:
            undescribed.append(node["name"])
        rows.append((node["name"], has_desc, len(described), len(cols)))
        total += len(cols)
        documented += len(described)

    width = max((len(r[0]) for r in rows), default=5)
    print(f"{'model'.ljust(width)}  model description  columns documented")
    for name, has_desc, d, n in rows:
        print(f"{name.ljust(width)}  {'yes' if has_desc else 'NO ':<17}  {d}/{n}")
    if not total:
        sys.exit("no built models found in catalog.json. Run `dbt build`, then `dbt docs generate`, then try again.")
    pct = 100 * documented / total
    shown = f"{int(pct)}%" if pct == int(pct) else f"{pct:.1f}%"  # never round 99.75 up to a passing "100%"
    print(f"\ncolumn documentation coverage: {documented}/{total} = {shown}")
    if not_in_catalog:
        print(f"not in catalog.json (not built?): {', '.join(not_in_catalog)}")

    if args.min is not None and pct < args.min:
        sys.exit(f"coverage {shown} is below the required {args.min:g}%")
    if args.min is not None and undescribed:
        sys.exit(f"models with no description: {', '.join(undescribed)}")
    if args.min is not None and not_in_catalog:
        sys.exit(f"models missing from catalog.json: {', '.join(not_in_catalog)}. "
                 "Run `dbt build`, then `dbt docs generate`.")


if __name__ == "__main__":
    main()
