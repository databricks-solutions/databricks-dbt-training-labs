#!/usr/bin/env python3
"""Generate the Module 5 documentation-and-governance seeds: a small CLEAN sample of Jaffle Shop data
plus one synthetic PII column.

Module 5 is about documenting and governing data, not about finding bad data, so unlike Module 4
there are no injected defects. What the labs need instead is something worth protecting, so this
script:

  1. samples a few customers and their orders from Lab 01's raw Jaffle Shop CSVs (deterministic),
  2. converts cents -> dollars and adds a synthetic `order_status` column,
  3. adds a synthetic `customer_email` (always on the reserved example.com domain), which is the PII
     the access-control labs tag, mask and restrict,
  4. writes seeds/*.csv, and
  5. checks the clean-data invariants the models and docs rely on, and fails loudly if one breaks.

Re-run it (output is byte-for-byte identical every time) if you change the sample:

    python3 scripts/generate_module5_seeds.py

Input : ../jaffle_shop/seeds/jaffle-data/raw_*.csv
Output: seeds/{customers,products,locations,orders,order_items}.csv
"""

import csv
import random
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE.parent.parent / "jaffle_shop" / "seeds" / "jaffle-data"
OUT = HERE.parent / "seeds"

N_CUSTOMERS = 30
N_ORDERS = 80
N_ITEMLESS = 2  # natural orders with no items (subtotal 0): the classic NULL-aggregate edge case

ORDER_STATUSES = ["delivered", "shipped", "placed", "returned", "cancelled"]
ORDER_STATUS_WEIGHTS = [70, 12, 8, 6, 4]


def read(name):
    with open(RAW / name, newline="") as f:
        return list(csv.DictReader(f))


def money(cents):
    return f"{cents / 100:.2f}"


def email_for(name, taken):
    """first.last@example.com (reserved test domain), made unique with a numeric suffix."""
    local = ".".join(re.sub(r"[^a-z]", "", part.lower()) for part in name.split()) or "customer"
    candidate, n = local, 1
    while candidate in taken:
        n += 1
        candidate = f"{local}{n}"
    taken.add(candidate)
    return f"{candidate}@example.com"


def write(name, header, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / name, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    print(f"{name}: {len(rows)} rows")


def main():
    rng = random.Random(5)

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
    customer_ids = sorted(rng.sample(eligible_customers, N_CUSTOMERS))

    pool = sorted((o for c in customer_ids for o in orders_by_customer[c]), key=lambda o: o["id"])
    itemful = [o for o in pool if o["id"] in items_by_order]
    itemless = [o for o in pool if o["id"] not in items_by_order]
    chosen = rng.sample(itemless, N_ITEMLESS) + rng.sample(itemful, N_ORDERS - N_ITEMLESS)
    chosen.sort(key=lambda o: (o["ordered_at"], o["id"]))

    orders = [{
        "order_id": o["id"],
        "customer_id": o["customer"],
        "location_id": o["store_id"],
        "order_date": o["ordered_at"][:10],
        "order_status": rng.choices(ORDER_STATUSES, ORDER_STATUS_WEIGHTS)[0],
        "subtotal": int(o["subtotal"]),
        "tax_paid": int(o["tax_paid"]),
        "order_total": int(o["order_total"]),
    } for o in chosen]
    order_ids = {o["order_id"] for o in orders}
    items = [
        {"order_item_id": it["id"], "order_id": it["order_id"], "product_id": it["sku"]}
        for oid in sorted(order_ids) for it in items_by_order.get(oid, [])
    ]

    taken = set()
    customers = [{
        "customer_id": cid,
        "customer_name": raw_customers[cid]["name"],
        "customer_email": email_for(raw_customers[cid]["name"], taken),
    } for cid in customer_ids]

    # ---- 2. write -----------------------------------------------------------------------------
    write("customers.csv", ["customer_id", "customer_name", "customer_email"],
          [[c["customer_id"], c["customer_name"], c["customer_email"]] for c in customers])
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

    # ---- 3. self-check: the data is CLEAN, and the docs can say so ------------------------------
    cust_ids = [c["customer_id"] for c in customers]
    emails = [c["customer_email"] for c in customers]
    assert len(set(cust_ids)) == len(cust_ids), "customer_id must be unique"
    assert len(set(emails)) == len(emails), "customer_email must be unique"
    assert all(e.endswith("@example.com") for e in emails), "emails must stay on the reserved domain"
    assert all(c["customer_name"] for c in customers), "customer_name must not be empty"
    cust_set = set(cust_ids)
    item_total = defaultdict(int)
    for i in items:
        item_total[i["order_id"]] += price_cents[i["product_id"]]
    for o in orders:
        assert o["customer_id"] in cust_set, "every order has a customer"
        assert item_total.get(o["order_id"], 0) == o["subtotal"], "subtotal == sum(item prices)"
        assert o["order_total"] == o["subtotal"] + o["tax_paid"]
        assert o["tax_paid"] >= 0 and o["order_status"] in ORDER_STATUSES
    assert all(i["product_id"] in price_cents for i in items), "every item has a product"
    n_itemless = sum(1 for o in orders if o["order_id"] not in item_total)
    print(f"\nClean-data invariants hold. (item-less orders, legitimately subtotal 0: {n_itemless})")


if __name__ == "__main__":
    main()
