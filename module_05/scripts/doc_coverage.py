#!/usr/bin/env python3
"""Report how much of the project is documented, from dbt's own artifacts.

Run `dbt docs generate` first: it writes target/catalog.json (the columns that REALLY exist in the
warehouse) next to target/manifest.json (the descriptions you wrote). Comparing the two is the only
way to catch a column that exists in Unity Catalog but has no description in dbt.

    python3 scripts/doc_coverage.py                  # print the table
    python3 scripts/doc_coverage.py --min 100        # exit 1 if coverage < 100% (a CI gate)

Only models that exist in the warehouse are counted: this project's tables and views, not seeds, tests,
package models or ephemeral models (an ephemeral model has no table, so it has no catalog entry and
its columns cannot be checked against what really exists). With --min, a built model with no
model-level description also fails the gate.
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

    rows, total, documented, undescribed = [], 0, 0, []
    for uid, node in sorted(manifest["nodes"].items()):
        if node["resource_type"] != "model" or node["package_name"] != manifest["metadata"]["project_name"]:
            continue
        built = catalog["nodes"].get(uid)
        if built is None:  # ephemeral models never exist in the warehouse, so they have no catalog entry
            continue
        cols = list(built["columns"])
        yml = node["columns"]
        described = [c for c in cols if (yml.get(c.lower(), yml.get(c, {})).get("description") or "").strip()]
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
    print(f"\ncolumn documentation coverage: {documented}/{total} = {pct:.0f}%")

    if args.min is not None and pct < args.min:
        sys.exit(f"coverage {pct:.0f}% is below the required {args.min:.0f}%")
    if args.min is not None and undescribed:
        sys.exit(f"models with no description: {', '.join(undescribed)}")


if __name__ == "__main__":
    main()
