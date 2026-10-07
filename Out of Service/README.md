# Out of Service

A custom case about the night Lindenhall Bank's ATM network lost its link to
the ledger, and the one customer who walked away with more cash than their
account held.

Every machine holds three cassettes, so a withdrawal is logged the way the
machine counts it out — one column per note, `n1000`, `n500` and `n100`. What
somebody actually took is `n1000*1000 + n500*500 + n100*100`, which keeps every
amount a whole number of dollars and the case clear of fractions.

Account numbers are six digits, machines four, and every transaction carries a
twelve digit reference. None of them carries information — an account number
says nothing about its balance, a reference nothing about its amount — so
sorting by either teaches a player nothing.

`balance` is not the balance now. It is the figure each machine had last synced
before the crash, and the figure it went on checking withdrawals against all
night, one transaction at a time.

## Solution

```sql
SELECT a.name
FROM withdrawals w
JOIN accounts a ON a.account_id = w.account_id
GROUP BY a.account_id, a.name, a.balance
HAVING SUM(w.n1000*1000 + w.n500*500 + w.n100*100) > a.balance;
```

`Edric Pennal`, who took $13,000 across five transactions against a balance
of $12,730 — $270 over.

Valuing each cassette separately works just as well:
`SUM(n1000*1000) + SUM(n500*500) + SUM(n100*100) > balance`.

`out_of_service.py` seeds its random number generator, so rebuilding reproduces
this exact database — the figures quoted here and on the evidence artwork stay
true.

## What makes it hard

The overdraw exists only as a total, and every shortcut points somewhere else:

- **One row at a time accuses nobody.** No single withdrawal is larger than the
  balance it was checked against — the culprit's largest is 4,000 against
  12,730 — so `WHERE n1000*1000 + ... > balance` returns an empty table. That is
  what forces `GROUP BY`.
- **`>=` accuses eight.** Seven accounts were emptied to exactly zero that
  night, so their total equals their balance. Only `>` names one customer.
- **Forgetting a cassette accuses nobody.** The culprit is $270 over, which
  is less than the $500 they took in hundreds and less than the $1,500 they
  took in five hundreds. Drop either column from the sum and they fall back
  inside their balance.
- **Counting notes accuses nobody either**, and the night's biggest pile — 47
  notes, all hundreds — belongs to an account that stayed well in credit. Six
  customers took more notes than the culprit.
- **Both rankings arrest the wrong customer.** Five customers took more cash
  than the culprit, the largest $16,000 against a balance of $46,800, and
  another filed seven transactions to the culprit's five. Sorting by either one
  puts somebody innocent at the top.
- **Nine accounts were never touched**, so they have no rows in `withdrawals`
  at all and a `LEFT JOIN` has to cope with `NULL`.

60 accounts, 131 transactions logged between 19:41 and midnight. The machine's
own cap of $4,000 per transaction holds across every row, though nothing in
the puzzle turns on it. The three note values do: they are on the evidence and
nowhere in the database, so without that card the case cannot be worked at all.

## Workshop description

> The link between the cash machines and the ledger went down at 19:41. The
> machines did not stop. Each one kept approving withdrawals against the
> balance it had last synced before the crash, checking them one transaction at
> a time and never adding them up.
>
> One customer worked out what that meant and kept going.
>
> The log records a withdrawal the way a machine counts it out: a column for
> the thousand dollar notes, a column for the five hundreds, a column for the
> hundreds. Nobody took more in one go than their account held — that would
> have been refused. Find the customer whose night came to more than they had.
>
> Sixty accounts, one night, three cassettes. Every obvious shortcut arrests
> somebody innocent.

## Rebuilding

Both commands write into this folder. Run them from the repository root:

```bash
python3 "Sources/Out of Service/out_of_service.py"   # the database
"Sources/Out of Service/build.sh"                    # the artwork (needs rsvg-convert)
```

`out_of_service.py` re-checks every property above and refuses to finish if one
breaks, so a regenerated database is always solvable.
