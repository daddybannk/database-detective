# Where Are You?

A custom case about the one household in Sunridge Estates that never paid its
annual common area maintenance fee. The player gets a witness photograph of the
house and has to turn it into a `WHERE` clause.

## Solution

```sql
SELECT owner FROM households
WHERE house_number LIKE '3%13'
  AND floors = 1
  AND roof_color = 'Red'
  AND wall_color = 'White'
  AND door_color = 'Black'
  AND fence_color = 'Brown'
  AND house_number NOT IN (SELECT house_number FROM fee_payments);
```

`Dodge Hollings`, at 34713.

Both halves are needed. Five houses match the photograph, so the description
alone leaves four innocent owners; 32 houses never paid, so the ledger alone
leaves 31. Every clue is load bearing too — for each one there is an unpaid
house matching the other five, so dropping a clue always returns more than one
suspect. `31347` is there to punish `LIKE '3%13%'`.

## Rebuilding

Both commands write into this folder. Run them from the repository root:

```bash
python3 "Sources/Where Are You/where.py"   # the database
"Sources/Where Are You/build.sh"           # the artwork (needs rsvg-convert)
```

`where.py` re-checks every property above and refuses to finish if one breaks,
so a regenerated database is always solvable.
