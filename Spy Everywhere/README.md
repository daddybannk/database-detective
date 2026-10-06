# Spy Everywhere

A custom case about the spy who infiltrated Lindenhall Community Hall by
signing up for every one of its activity groups.

Ten groups meet two to an evening, five evenings a week, so no member can
attend more than five of them. One member filed a sheet for all ten anyway --
not to take part, but to have a reason to be in the building whichever evening
something happens. That sheet for the pottery studio is the cover story, and
the only trace the spy leaves is the sign-up book itself.

Dates are whole numbers stamped `YYYYMMDD` -- `20260304` is the 4th of March
2026 -- and the sign-up desk only opens on weekdays, so no date in the database
falls at a weekend.

## Solution

```sql
SELECT m.name
FROM members m
JOIN signups s ON s.member_id = m.member_id
GROUP BY m.member_id, m.name
HAVING COUNT(DISTINCT s.activity_id) = 10;
```

`James Bond`, the spy, who filed eleven of the term's 329 sheets, covering all
ten groups.

`spy_everywhere.py` seeds its random number generator, so rebuilding
reproduces this exact database -- the figures quoted here and on the evidence
artwork stay true.

## What makes it hard

One trap, pointing at everybody except the culprit. A member who renews a group
later in the term files a second sheet for it, so counting sheets is not the
same as counting groups:

- **`COUNT(*) = 10` accuses four members and never the culprit.** Those four
  filed ten sheets across nine groups, which is exactly what makes that query
  look as though it worked.
- **`COUNT(*) >= 10` accuses five**, the culprit among them, so it still does
  not say which one to arrest.
- **`COUNT(DISTINCT activity_id) >= 9` accuses eleven.** Six more members
  reached nine groups with nine sheets, and the four above are in nine groups
  too, so settling for `>= 9` catches ten innocent members.
- **Twelve members never signed up for anything.** They have no rows in
  `signups` at all, so a `LEFT JOIN` has to cope with `NULL`.

Two things are kept true by construction so none of those counts depends on the
draw: every ordinary member stays below nine groups and below nine sheets, and
the culprit's eleven dates are spread across 278 days of the term without ever
being the earliest or the latest sheet on file. Sorting by `signup_date`
therefore points at nobody -- counting distinct groups is the only way through.

The thinnest group roster is 24 members, so no group is small enough to read
the answer off directly either.

## Rebuilding

Both commands write into this folder. Run them from the repository root:

```bash
python3 "Sources/Spy Everywhere/spy_everywhere.py"   # the database
"Sources/Spy Everywhere/build.sh"                     # the artwork (needs rsvg-convert)
```

`spy_everywhere.py` re-checks every property above and refuses to finish if one
breaks, so a regenerated database is always solvable.
