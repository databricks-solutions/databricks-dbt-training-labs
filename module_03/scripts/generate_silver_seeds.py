#!/usr/bin/env python3
"""Generate the Module 3 silver seed CSVs from Lab 01's raw Jaffle Shop data.

Module 3 ships silver as seeds so learners can build gold labs without running a bronze
pipeline. Rather than hand-maintaining ~150k rows of cleaned data, we derive the
seeds deterministically from Lab 01's raw CSVs by applying the same cleaning a bronze→silver step
would (cents → decimal dollars, timestamps → dates, renames, food/drink
flags). Re-run this whenever the raw data changes:

    python3 scripts/generate_silver_seeds.py

Input : ../jaffle_shop/seeds/jaffle-data/raw_*.csv
Output: seeds/silver_*.csv

These seeds ARE the silver layer: loaded into a globally named `silver` schema, they are read
directly by the gold and incremental labs via source('silver', ...). There are no silver models.

The money columns are written with two decimals and loaded as DECIMAL(16,2) via column_types in
seeds/_seed_properties.yml, so `order_total = subtotal + tax_paid` holds exactly.
"""

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE.parent.parent / "jaffle_shop" / "seeds" / "jaffle-data"
OUT = HERE.parent / "seeds"


def cents_to_dollars(cents: str) -> str:
    return f"{int(cents) / 100:.2f}"


def date_only(ts: str) -> str:
    return ts[:10]


def read(name: str):
    with open(RAW / name, newline="") as f:
        return list(csv.DictReader(f))


def write(name: str, header, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"{name}: {len(rows)} rows")


def main():
    # silver_customers: pure rename
    customers = read("raw_customers.csv")
    write(
        "silver_customers.csv",
        ["customer_id", "customer_name"],
        [[c["id"], c["name"]] for c in customers],
    )

    # silver_locations: rename + opened_at date + tax_rate
    stores = read("raw_stores.csv")
    write(
        "silver_locations.csv",
        ["location_id", "location_name", "opened_at", "tax_rate"],
        [[s["id"], s["name"], date_only(s["opened_at"]), s["tax_rate"]] for s in stores],
    )

    # silver_products: dollars + food/drink flags (description dropped)
    products = read("raw_products.csv")
    write(
        "silver_products.csv",
        ["product_id", "product_name", "product_type", "product_price", "is_food_item", "is_drink_item"],
        [
            [
                p["sku"],
                p["name"].strip(),
                p["type"],
                cents_to_dollars(p["price"]),
                str(p["type"] == "jaffle").lower(),
                str(p["type"] == "beverage").lower(),
            ]
            for p in products
        ],
    )

    # silver_orders: rename + order_date + dollars
    orders = read("raw_orders.csv")
    write(
        "silver_orders.csv",
        ["order_id", "customer_id", "location_id", "order_date", "subtotal", "tax_paid", "order_total"],
        [
            [
                o["id"],
                o["customer"],
                o["store_id"],
                date_only(o["ordered_at"]),
                cents_to_dollars(o["subtotal"]),
                cents_to_dollars(o["tax_paid"]),
                cents_to_dollars(o["order_total"]),
            ]
            for o in orders
        ],
    )

    # silver_order_items: pure rename
    items = read("raw_items.csv")
    write(
        "silver_order_items.csv",
        ["order_item_id", "order_id", "product_id"],
        [[i["id"], i["order_id"], i["sku"]] for i in items],
    )


if __name__ == "__main__":
    main()
