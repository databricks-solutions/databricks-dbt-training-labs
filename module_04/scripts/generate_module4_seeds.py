#!/usr/bin/env python3
"""Generate the Module 4 testing-lab seeds: a small clean sample of Jaffle Shop data with a
documented catalog of KNOWN defects injected on purpose.

Every Module 4 lab needs data that is realistic, tiny (fast to reseed), self-contained (no output
from earlier modules), and deliberately imperfect in ways we can name. So this script:

  1. samples a few customers and their orders from Lab 01's raw Jaffle Shop CSVs (deterministic),
  2. converts cents -> dollars and adds a synthetic `order_status` column,
  3. injects a catalog of defects D01..D07, each tied to the kind of test that should catch it,
  4. writes seeds/*.csv, including seeds/defect_catalog.csv (the answer key), and
  5. re-derives every defect count from the written data and fails loudly if it disagrees.

Re-run it (output is byte-for-byte identical every time) if you change the sample or defects:

    python3 scripts/generate_module4_seeds.py

Input : ../jaffle_shop/seeds/jaffle-data/raw_*.csv
Output: seeds/{customers,products,locations,orders,order_items,defect_catalog}.csv
"""

import csv
import random
import uuid
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE.parent.parent / "jaffle_shop" / "seeds" / "jaffle-data"
OUT = HERE.parent / "seeds"

N_CUSTOMERS = 30
N_ORDERS = 80
N_ITEMLESS = 2  # natural orders with no items (subtotal 0): the classic NULL-aggregate edge case

# D06: how far each of 4 orders' subtotal is nudged away from the sum of its item prices (cents).
D06_DELTAS_CENTS = [150, -100, 225, -75]

ORDER_STATUSES = ["delivered", "shipped", "placed", "returned", "cancelled"]
ORDER_STATUS_WEIGHTS = [70, 12, 8, 6, 4]
ORPHAN_CUSTOMER_ID = "00000000-0000-0000-0000-000000000000"
ORPHAN_PRODUCT_ID = "XXX-999"


def read(name):
    with open(RAW / name, newline="") as f:
        return list(csv.DictReader(f))


def money(cents):
    return f"{cents / 100:.2f}"


def write(name, header, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / name, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    print(f"{name}: {len(rows)} rows")


def main():
    rng = random.Random(4)

    raw_customers = {r["id"]: r for r in read("raw_customers.csv")}
    raw_stores = read("raw_stores.csv")
    raw_products = read("raw_products.csv")
    raw_orders = read("raw_orders.csv")
    raw_items = read("raw_items.csv")

    price_cents = {p["sku"]: int(p["price"]) for p in raw_products}
    items_by_order = defaultdict(list)
    for it in raw_items:
        items_by_order[it["order_id"]].append(it)
    orders_by_customer = defaultdict(list)
    for o in raw_orders:
        orders_by_customer[o["customer"]].append(o)

    # ---- 1. sample ----------------------------------------------------------------------------
    eligible_customers = sorted(c for c, os_ in orders_by_customer.items() if len(os_) >= 3)
    customer_ids = rng.sample(eligible_customers, N_CUSTOMERS)

    pool = sorted((o for c in customer_ids for o in orders_by_customer[c]), key=lambda o: o["id"])
    itemful = [o for o in pool if o["id"] in items_by_order]
    itemless = [o for o in pool if o["id"] not in items_by_order]
    chosen = rng.sample(itemless, N_ITEMLESS) + rng.sample(itemful, N_ORDERS - N_ITEMLESS)
    chosen.sort(key=lambda o: (o["ordered_at"], o["id"]))

    # Working rows (cents as ints, so injected defects stay exact).
    orders = []
    for o in chosen:
        orders.append({
            "order_id": o["id"],
            "customer_id": o["customer"],
            "location_id": o["store_id"],
            "order_date": o["ordered_at"][:10],
            "order_status": rng.choices(ORDER_STATUSES, ORDER_STATUS_WEIGHTS)[0],
            "subtotal": int(o["subtotal"]),
            "tax_paid": int(o["tax_paid"]),
            "order_total": int(o["order_total"]),
        })
    order_ids = {o["order_id"] for o in orders}
    items = [
        {"order_item_id": it["id"], "order_id": it["order_id"], "product_id": it["sku"]}
        for oid in sorted(order_ids) for it in items_by_order.get(oid, [])
    ]
    customers = [
        {"customer_id": cid, "customer_name": raw_customers[cid]["name"]} for cid in sorted(customer_ids)
    ]

    # Baseline invariant: the CLEAN sample satisfies every rule we later break on purpose.
    for o in orders:
        got = sum(price_cents[i["product_id"]] for i in items if i["order_id"] == o["order_id"])
        assert got == o["subtotal"], "clean sample must satisfy subtotal == sum(item prices)"
        assert o["order_total"] == o["subtotal"] + o["tax_paid"]

    # ---- 2. inject the defect catalog ---------------------------------------------------------
    catalog = []  # (defect_id, table_name, row_key, rule_violated, caught_by)

    victims = rng.sample([o for o in orders if o["subtotal"] > 0], 1 + 1 + 1 + len(D06_DELTAS_CENTS) + 2)
    d03, d04, d05, *rest = victims
    d06, d07 = rest[: len(D06_DELTAS_CENTS)], rest[len(D06_DELTAS_CENTS):]

    # D01 customers.customer_name is NULL
    c1 = rng.choice(customers)
    c1["customer_name"] = ""  # blank cell -> NULL when seeded
    catalog.append(("D01", "customers", c1["customer_id"], "customer_name must not be null",
                    "generic test: not_null"))

    # D02 customers.customer_id appears twice (a duplicated key)
    c2 = rng.choice([c for c in customers if c is not c1])
    customers.append(dict(c2))
    catalog.append(("D02", "customers", c2["customer_id"], "customer_id must be unique",
                    "generic test: unique"))

    # D03 orders.customer_id has no matching customer (orphan foreign key)
    d03["customer_id"] = ORPHAN_CUSTOMER_ID
    catalog.append(("D03", "orders", d03["order_id"], "customer_id must exist in customers",
                    "generic test: relationships"))

    # D04 orders.order_status is outside the allowed set (a typo)
    d04["order_status"] = "delivred"
    catalog.append(("D04", "orders", d04["order_id"],
                    "order_status must be one of placed/shipped/delivered/returned/cancelled",
                    "generic test: accepted_values"))

    # D05 orders.tax_paid is negative (order_total stays = subtotal + tax_paid, so ONLY this rule breaks)
    d05["tax_paid"] = -max(d05["tax_paid"], 50)
    d05["order_total"] = d05["subtotal"] + d05["tax_paid"]
    catalog.append(("D05", "orders", d05["order_id"], "tax_paid must be >= 0",
                    "Delta CHECK constraint / expression_is_true"))

    # D06 orders.subtotal != sum of the order's item prices (order_total kept consistent)
    for o, delta in zip(d06, D06_DELTAS_CENTS):
        o["subtotal"] += delta
        o["order_total"] = o["subtotal"] + o["tax_paid"]
        catalog.append(("D06", "orders", o["order_id"], "subtotal must equal the sum of its item prices",
                        "singular SQL test (Lab 4.3)"))

    # D07 order_items.product_id references a SKU that is not in products (a discontinued/unknown SKU)
    for o in d07:
        item_id = str(uuid.UUID(int=rng.getrandbits(128), version=4))
        items.append({"order_item_id": item_id, "order_id": o["order_id"], "product_id": ORPHAN_PRODUCT_ID})
        catalog.append(("D07", "order_items", item_id, "product_id must exist in products",
                        "generic test: relationships (try severity: warn)"))

    # ---- 3. write -----------------------------------------------------------------------------
    write("customers.csv", ["customer_id", "customer_name"],
          [[c["customer_id"], c["customer_name"]] for c in customers])
    write("products.csv", ["product_id", "product_name", "product_type", "product_price"],
          [[p["sku"], p["name"].strip(), p["type"], money(int(p["price"]))] for p in raw_products])
    write("locations.csv", ["location_id", "location_name", "opened_at", "tax_rate"],
          [[s["id"], s["name"], s["opened_at"][:10], s["tax_rate"]] for s in raw_stores])
    write("orders.csv",
          ["order_id", "customer_id", "location_id", "order_date", "order_status",
           "subtotal", "tax_paid", "order_total"],
          [[o["order_id"], o["customer_id"], o["location_id"], o["order_date"], o["order_status"],
            money(o["subtotal"]), money(o["tax_paid"]), money(o["order_total"])] for o in orders])
    write("order_items.csv", ["order_item_id", "order_id", "product_id"],
          [[i["order_item_id"], i["order_id"], i["product_id"]] for i in items])
    write("defect_catalog.csv", ["defect_id", "table_name", "row_key", "rule_violated", "caught_by"],
          [list(row) for row in catalog])

    # ---- 4. self-check: re-derive every documented count from the data we just wrote ----------
    cust_ids = [c["customer_id"] for c in customers]
    n_null_name = sum(1 for c in customers if not c["customer_name"])
    n_dupe_keys = len(cust_ids) - len(set(cust_ids))
    n_orphan_cust = sum(1 for o in orders if o["customer_id"] not in set(cust_ids))
    n_bad_status = sum(1 for o in orders if o["order_status"] not in ORDER_STATUSES)
    n_neg_tax = sum(1 for o in orders if o["tax_paid"] < 0)
    n_mismatch = 0
    for o in orders:
        got = sum(price_cents.get(i["product_id"], 0) for i in items if i["order_id"] == o["order_id"])
        n_mismatch += got != o["subtotal"]
    n_orphan_sku = sum(1 for i in items if i["product_id"] not in price_cents)
    n_itemless = sum(1 for o in orders if not any(i["order_id"] == o["order_id"] for i in items))
    expected = dict(D01=n_null_name, D02=n_dupe_keys, D03=n_orphan_cust, D04=n_bad_status,
                    D05=n_neg_tax, D06=n_mismatch, D07=n_orphan_sku)
    in_catalog = {d: sum(1 for c in catalog if c[0] == d) for d in expected}
    assert expected == in_catalog, f"catalog out of sync with data: {expected} vs {in_catalog}"
    print("\nDefects re-derived from the written data (all match the catalog):")
    for d, n in expected.items():
        print(f"  {d}: {n}")
    print(f"  (item-less orders, legitimately subtotal 0: {n_itemless})")


if __name__ == "__main__":
    main()
