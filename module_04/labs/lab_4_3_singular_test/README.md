# Lab 4.3: Singular SQL Test

Generic tests (`not_null`, `unique`, `relationships`, `accepted_values`) check one column of one
table. Some business rules cannot be expressed that way. In this lab you write a **singular test**: a
plain SQL query that returns the rows that break a rule. If it returns no rows, the test passes. You
will watch it fail on known bad data, diagnose why, and then make it pass.

**Before you start:** complete the setup in the [module README](../../README.md) so that `dbt build`
runs green in your schema. The fixtures for this lab (and their known defects) are already seeded.

## What you will learn

- When a rule needs a **singular test** instead of a generic test.
- How a singular test works: it returns the *violating rows*, and **zero rows means pass**.
- How to run it with `dbt test`, read a failing result, and save the failures with `--store-failures`.
- Why a `NULL` comparison can silently hide rows, and how `left join` plus `coalesce` fixes it.
- Why a `--vars` value applies when a model is *built*, not when a test *runs*.

## What's in this folder

| File | Purpose |
|------|---------|
| `README.md` | This lab guide. |
| `solution/assert_order_subtotal_matches_items.sql` | The reference answer. Peek only after you have tried. |

The **starter** is [`data-tests/assert_order_subtotal_matches_items.sql`](../../data-tests/assert_order_subtotal_matches_items.sql):
a placeholder that returns no rows, so `dbt build` stays green until you replace it. The solution lives
outside `test-paths`, so dbt ignores it until you copy it over the starter.

## The business rule

> An order's `subtotal` must equal the sum of the list prices of the items on that order.

This needs a join (`stg_orders` to `stg_order_items` to `stg_products`) and an aggregate (`sum`), so no
generic test can check it.

The seeded data has **four** orders that break this rule on purpose (defect **D06** in the
[defect catalog](../../README.md#known-defects)). It also has two orders that legitimately have **no
items** and a subtotal of 0: an edge case, not a defect.

## Lab steps

Run everything from the module root (`module_04/`) with your environment exported:

```bash
set -a && source .env && set +a
```

### 1. Define the rule

Say it in one sentence: *subtotal equals the sum of the item prices*. Then work out what you need:
the total of each order's item prices, compared with the order's `subtotal`.

### 2. Write the failure-returning SQL

Open the starter and replace the placeholder with a query that returns the orders that break the rule.
A good shape:

1. A CTE that totals item prices per order (join `stg_order_items` to `stg_products`, `group by order_id`).
2. A select from `stg_orders` that compares `subtotal` to that total.
3. A `where` clause that keeps only the orders where they **differ**.

Use `ref()` for every table, and do not end the query with a semicolon. Stuck? The answer is in
[`solution/`](solution/assert_order_subtotal_matches_items.sql).

### 3. Run it and watch it fail

```bash
dbt test --select assert_order_subtotal_matches_items
```

The test **fails** and reports 4 results: one row per planted D06 order. A failing singular test is
the point: it found real bad data.

### 4. Diagnose the failures

Save the failing rows to a table you can query:

```bash
dbt test --select assert_order_subtotal_matches_items --store-failures
```

dbt writes them to a table named after the test, in a schema called `<your_schema>_dbt_test__audit`,
so the full name is `<your_catalog>.<your_schema>_dbt_test__audit.assert_order_subtotal_matches_items`.
Then:

- Query the stored rows. They hold the columns your test selected, so compare `subtotal` with
  `items_subtotal` and look at `difference` for each order.
- Cross-check the answer key:
  `select * from <your_catalog>.<your_schema>.defect_catalog where defect_id = 'D06'`. The same four
  `order_id`s should be listed. Your test found exactly what was planted.
- Think about the two item-less orders. They have no row in the item totals, so their total is `NULL`.
  Without `coalesce`, `subtotal <> NULL` is neither true nor false and the row is silently dropped.
  That would also hide an item-less order claiming a *non-zero* subtotal.

### 5. Make it pass

`stg_orders` has a switch that excludes the four D06 orders listed in `defect_catalog`. It is a
**view**, so a `--vars` value is applied when the view is *built*, not when a test runs. So rebuild
the view with the var first, then rerun the test:

```bash
dbt run --select stg_orders --vars '{"quarantine_subtotal_defects": true}'
dbt test --select assert_order_subtotal_matches_items
```

The same test now returns 0 rows and **passes**.

Run these as two commands. A single `dbt build --select stg_orders assert_order_subtotal_matches_items`
would also run any generic tests on `stg_orders`, and the ones for D03, D04 and D05 still fail, so it
would exit with an error even though this lab's test passed.

**Restore the view before you move on.** `fct_orders` is a table and these commands do not rebuild it,
so it still has the D06 orders. But anything rebuilt from `stg_orders` while the quarantine is in place,
`fct_orders` included, loses them and changes the counts in later labs. To put the original data back:

```bash
dbt run --select stg_orders
```

## Check your work

| You should be able to show | How |
|---|---|
| A valid singular test in `data-tests/` | It compiles and `dbt test` runs it. |
| A **failing** outcome | Step 3: 4 rows returned, test fails. |
| A **passing** outcome | Step 5: 0 rows returned, test passes. |
| You can explain why it fails | The 4 rows match `defect_catalog` (D06). |

## Gotchas

- **A singular test passes on zero rows.** Every returned row is a failure.
- **`NULL` comparisons drop rows.** Use `left join` plus `coalesce` when a side may be missing.
- **Vars apply at build time.** Rebuild the view with the var first, then run the test.
- **No trailing semicolon.** dbt wraps your query to count its rows, so a `;` gives a
  `PARSE_SYNTAX_ERROR`. That is an **ERROR**, not a **FAIL**: the test never ran, so do not read it as
  "the data is bad".
- **Use `ref()`,** not table names, so dbt runs the test after the models it reads.
