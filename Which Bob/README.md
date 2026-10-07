# Which Bob?

A custom case about a threatening letter signed with a first name, and the
three hundred officers on the roster who answer to it. The man who wrote it was
an officer here until the force let him go last month, and that is the whole of
what anybody remembers — not his surname, not his badge number.

Records has never deleted a row from `officers`, so a dismissed man sits in the
roster looking exactly like one who came in this morning, and no column says
which. The fingerprint scanner on the staff door is the only thing that knows
the difference, and it knows it only by what it did not record.

Today is 7 October 2026 and the log starts 1 September. Dates are `YYYYMMDD`
and times `HHMM`, both whole numbers. Badge and scan numbers carry no
information beyond identity and the order of the log, so sorting by either
teaches a player nothing.

## Solution

```sql
SELECT o.first_name, o.last_name
FROM officers o
JOIN fingerprint_scans s ON s.badge_id = o.badge_id
WHERE o.first_name = 'Bob'
GROUP BY o.badge_id
HAVING MAX(s.date) < 20261001;
```

`Bob Leeswagger`, badge 53271, a sergeant in Traffic whose last shift began at
22:27 on 30 September — the day he was dismissed, and the last trace of him in
the building.

Every officer on the roster has at least one scan in the log, which is what
lets every other shape of the same question agree with this one. A set
difference asks it without grouping anything at all:

```sql
SELECT r.badge_id, first_name, last_name
FROM (SELECT DISTINCT badge_id FROM fingerprint_scans WHERE date < 20261001
      EXCEPT
      SELECT DISTINCT badge_id FROM fingerprint_scans WHERE date >= 20261001) AS r
JOIN officers AS o ON o.badge_id = r.badge_id
WHERE first_name = 'Bob';
```

So does `NOT IN`:

```sql
SELECT first_name, last_name FROM officers
WHERE first_name = 'Bob' AND badge_id NOT IN (
    SELECT badge_id FROM fingerprint_scans WHERE date >= 20261001);
```

and so does `LEFT JOIN ... WHERE s.scan_id IS NULL`. All four name one man, and
`> 20260930` works wherever `>= 20261001` does.

The set difference is the sturdiest of the four, because it only ever considers
officers the scanner actually recorded last month: it could not accuse a man
with no scans at all, where `NOT IN` and the `LEFT JOIN` both would. Nothing in
this database has none — `duty_days()` sees to that — but a case built on an
absence should know which of its solutions depends on that and which does not.

`which_bob.py` seeds its random number generator, so rebuilding reproduces this
exact database — the figures quoted here and on the evidence artwork stay true.

## What makes it hard

What identifies the man is an absence, and nothing a player asks about this
month can see an absence:

- **Asking about this month accuses nobody.** He has no scan on or after 1
  October — not a late one, not an early one, none at all. Every query that
  reaches for *his most recent scan this month* comes back empty, and 299 Bobs
  answer the same question perfectly well. That is what forces a player to ask
  each Bob when he was last seen instead.
- **Forgetting the first name accuses eight.** Seven other officers also
  stopped coming in last month. Six of them have ordinary first names and one
  of them is a Bobby.
- **`LIKE 'Bob%'` accuses two.** Forty officers on the roster are called
  Bobby, and the one who left last month is caught by the prefix. Only
  `first_name = 'Bob'` names one man.
- **Being strict about the 30th accuses nobody named Bob.** His last shift was
  30 September itself, so `MAX(date) < 20260930` loses him and keeps the six
  who left earlier in the month.
- **Being loose about the turn of the month accuses four innocent men.** Four
  Bobs were last seen on 1 October — gone, or on leave, but gone *this* month,
  which is not what the station remembers. They are the four a player finds by
  asking which Bob has not been seen for longest *of those still scanning*.
- **Counting scans arrests the wrong Bob at either end.** The thinnest record
  in the log belongs to a Bob sworn in at the end of September with two scans
  to his name; the busiest has twenty-one. The culprit has twelve, with 161
  Bobs below him and 97 above.
- **Last month alone accuses all 300.** Every Bob worked some part of
  September, the culprit included, so September narrows nothing by itself.
- **The strange surname is not the odd one out.** Eight other Bobs carry
  surnames that are nowhere in the station's usual stock of them, and all eight
  scanned in this month. Picking the unusual name out of three hundred by eye
  arrests somebody innocent.

520 officers — 300 Bobs, 40 Bobbys, 180 everybody else — and 5,773 scans
logged between 1 September and this morning. Nobody clocks in twice in a day,
so a row is a shift.

## Workshop description

> The letter was in this morning's post. It promises to deal with every last
> one of us, and it is signed with a first name: Bob.
>
> He was one of ours until the force let him go last month. Nobody can
> remember his surname. Three hundred officers on our roster are called Bob,
> and the roster will not help you narrow it — Records has never deleted a row
> from it, so the men who were dismissed are still listed beside the men who
> came in this morning, and nothing says which is which.
>
> The scanner on the staff door is the only thing in this building that knows
> who still works here. He was sacked on the 30th. Today is the 7th.
>
> Three hundred Bobs, five thousand scans, and the one that matters was never
> taken.

## Rebuilding

Both commands write into this folder. Run them from the repository root:

```bash
python3 "Sources/Which Bob/which_bob.py"   # the database
"Sources/Which Bob/build.sh"               # the artwork (needs rsvg-convert)
```

`which_bob.py` re-checks every property above and refuses to finish if one
breaks, so a regenerated database is always solvable.
