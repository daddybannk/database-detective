# One Dollar

A custom case about the member of Zora Mart who paid a dollar less than their
basket came to.

Prices are whole dollars stored as `INTEGER`. The game does not render
decimals, and SQLite would decide a fractional comparison by floating point
error anyway, so there are no fractions anywhere in the database.

## Solution

```sql
SELECT m.name
FROM members m
JOIN purchases pu ON pu.member_id = m.member_id
JOIN products  p  ON p.product_id = pu.product_id
JOIN payments  pa ON pa.member_id = m.member_id
GROUP BY m.member_id, m.name
HAVING SUM(p.price) - pa.paid = 1;
```

`Buck Mulgrew`, whose basket rings up $20 against $19 paid.

`one_dollar.py` seeds its random number generator, so rebuilding reproduces
this exact database — the figures quoted here and on the evidence artwork stay
true.

## What makes it hard

Three traps sit between the player and that query:

- **Repeat purchases.** Every scanned item is its own row, and the culprit took
  two jars of Strawberry Jam. `SUM(DISTINCT price)` reads their basket as $15
  instead of $20, so they drop out and the query returns nothing at all.
- **Members who never shopped.** 25 members have no rows in `purchases` and
  none in `payments`, so a `LEFT JOIN` has to cope with `NULL`.
- **Overpayers.** 18 members handed over too much, one of them by exactly a
  dollar. `basket <> paid` returns 19 rows and `ABS(basket - paid) = 1` returns
  2, so the player has to get the direction right.

The audit is not short overall — the registers are $76 **over**, because the
overpayers more than cover the missing dollar. That is why the evidence is a
per-member exception report rather than a till reconciliation.

## Rebuilding

Both commands write into this folder. Run them from the repository root:

```bash
python3 "Sources/One Dollar/one_dollar.py"   # the database
"Sources/One Dollar/build.sh"                # the artwork (needs rsvg-convert)
```

`one_dollar.py` re-checks every property above and refuses to finish if one
breaks, so a regenerated database is always solvable.
