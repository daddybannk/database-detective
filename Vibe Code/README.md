# Vibe Code 👉👈

A custom case about a new starter who asked an AI for a migration, ran it
against production, and left the company with one table.

At 18:41 on Friday 9 October 2026 only `employees` was left standing: the
legacy key/value store the migration was meant to replace, which the script
never reached. One row per property per person, and the whole of the case:

```
emp_code | emp_property  | value
DOMN5523 | first_name    | David
DOMN5523 | last_name     | Brooks
DOMN5523 | department    | IT
DOMN5523 | role          | Manager
DOMN5523 | date_of_birth | 19960222
DOMN5523 | start_date    | 20261009
```

301 employees, six properties each, 1806 rows, every column TEXT.

## Solution

Three facts, from two cards: a **Junior**, in **IT**, who started on
**8 October** — the chat log is stamped the 9th and he calls it his second
day.

```sql
SELECT
    e.emp_code,
    e.value AS first_name,
    l.value AS last_name,
    r.value AS role,
    s.value AS start_date
FROM employees e
JOIN employees l ON e.emp_code = l.emp_code
JOIN employees d ON e.emp_code = d.emp_code
JOIN employees r ON e.emp_code = r.emp_code
JOIN employees s ON e.emp_code = s.emp_code
WHERE e.emp_property = 'first_name'
  AND l.emp_property = 'last_name'
  AND d.emp_property = 'department' AND d.value = 'IT'
  AND r.emp_property = 'role'       AND r.value = 'Junior'
  AND s.emp_property = 'start_date' AND s.value = '20261008'
ORDER BY s.value DESC;
```

One row: `Cole Finley`, staff code `NINX0359`, born 17 May 2004, on his
second day.

Five aliases — two to read the name back, three to carry a clue each. The
`ORDER BY` does nothing here, because there is only one row; it matters on the
second road in, below.

### The second road in

A player who never works the date out can drop it and sort instead. The
incident report calls him the **newest** Junior IT has taken on, and he is:

| Started | Name |
| ---: | :--- |
| **20261008** | **Cole Finley** |
| 20261002 | Wes Dickerson |
| … | *nine more, the newest of them from 2025* |

**There is no `LIMIT`, because the in-game console has none**, so this route
returns all eleven IT juniors and the answer is the top row. Both roads reach
the same man, and `verify()` checks both.

### If the console balks at a five-way self join

`SELECT emp_code FROM employees WHERE emp_property = 'start_date' AND value =
'20261008'` lists 35 codes, and the same query for `department`/`IT` lists 44.
Both come back in `emp_code` order, so they can be run down side by side;
seven codes are in both, and one lookup each settles which of the seven is the
Junior.

`vibe_code.py` seeds its random number generator, so rebuilding reproduces
this exact database — the figures quoted here and on the evidence artwork stay
true.

## What makes it hard

The first query a player writes cannot work, and it does not fail loudly — it
returns an empty table:

```sql
SELECT * FROM employees
WHERE emp_property = 'department' AND value = 'IT'
  AND emp_property = 'role'       AND value = 'Junior';   -- no rows, ever
```

One row holds one property, so asking a single row to be two things at once is
not a hard query but an impossible one. Nothing on the evidence says so; the
schema and that empty result say it between them, which is the `What is your
real name` lesson about not writing a card for what one query already tells
you.

Past that wall, **every clue is load bearing**, and the date is the one that
took work. A date is a narrow filter, so the day he started has to be crowded
or it answers on its own and leaves the other two clues decorative. Thirty
five people came in that Thursday:

- **Drop the role and seven answer.** Six others who started with him are in
  IT: they are seniors, interns and a manager, but the query cannot tell.
- **Drop the department and eleven answer.** Ten of his intake are juniors in
  other departments.
- **Drop the date and eleven answer** — every IT junior on the books. This is
  the only clue whose loss still leaves a road to him, because sorting those
  eleven puts him first. That is by design, not by luck.
- **The date alone answers with thirty five.** No second IT junior started
  that day, which is what makes all three clues together name exactly one.

The sort route has its own decoys, because without a `LIMIT` a player reads
the first row whatever they typed — so **the row a wrong sort puts first has
to be somebody innocent.** He started on the Thursday and eight people started
on the Friday after him, not one of them an IT junior:

- **Sort IT without filtering the role and the top row is `Dovid Brooks`** —
  the IT manager who started on the Friday, and the row quoted at the top of
  this file. `Trevor Gaines` the intern is above him as well.
- **Sort the juniors without filtering the department and four are above him**,
  all from the Friday.
- **Sort the whole payroll and all eight of the Friday are above him.**
- **An IT junior started six days before him.** `Wes Dickerson` on 2 October is
  the second row, so reading the sort is a judgement rather than a matter of
  spotting the only date in October — forty four people started that month.

And the rest:

- **Reading "the new kid" as the intern tops out at `Trevor Gaines`.** He is a
  real person, really in IT, and really did start that week, so the wrong
  instinct arrests somebody innocent rather than returning nothing — the
  `Step Bros` habit. The incident report says `Junior` in the word the system
  spells it with, and that is the only thing separating the two.
- **Filtering `value` without filtering `emp_property` is meaningless.**
  `value` is one column for every property, and `'20040517'` in it is Cole
  Finley's birthday on one row and `Felicita Womack`'s first day on another.
  The three clue values happen not to collide — `value = 'IT'` returns 44 rows
  and `value = 'Junior'` 82, all of them the right property — which is what
  keeps the evidence fair, but the hazard is in the table and a player who
  meets it has learned the point of the case.
- **`OR`ing the three clues returns 161 rows and names nobody.** They belong
  to 161 property slots spread over 133 different people.
- **Neither of the other orderings helps.** A staff code is drawn, not
  counted, so sorting by it says nothing about seniority: October's starters
  are scattered across 275 of the 301 places in that ordering, and the culprit
  sits in the middle of it. And he is not the youngest employee either — four
  summer graduates were born after him, so `ORDER BY value DESC` over
  `date_of_birth` finds one of them.

IT is the fifth largest of six departments at 44 people, and `Junior` the
second most common of four roles at 82, so neither clue is unusual enough to
narrow by hand.

**A case with a sort in it has to watch its ties.** SQL does not say which of
a tied group comes first, so `verify()` counts the rows *strictly* newer than
the culprit rather than reading his row position — a strictly newer row is the
only kind guaranteed to sit above him in every engine. His own Thursday holds
thirty five people, but no second IT junior, so the one sort that matters has
a unique top row.

## Workshop description

> Production is gone. All of it. At 18:41 somebody asked an AI for a migration
> to tidy up the employee table, and the AI wrote one, and they ran it against
> the live database without reading it.
>
> One table survived, and only because it was the ugly one the migration was
> meant to delete. It keeps a row per fact rather than a row per person, so
> there is no column called department and no column called role. There is a
> column called value, and it holds everything.
>
> Personnel is inside the system that is gone. The chat log has no names in
> it. The Head of IT can tell you a department and a job title, and the log
> can tell you the man had been there one day.
>
> Three facts, and no row to put them in. 👉👈

## Rebuilding

Both commands write into this folder. Run them from the repository root:

```bash
python3 "Sources/Vibe Code/vibe_code.py"  # the database
"Sources/Vibe Code/build.sh"              # the artwork
```

`vibe_code.py` re-checks every property above and refuses to finish if one
breaks, so a regenerated database is always solvable.

`build.sh` is the only one in this repository that does not use
`rsvg-convert`. The cards carry 👉👈, and Apple Color Emoji is an `sbix`
font — its colour lives in a bitmap table that cairo, which rsvg draws text
through, does not read. rsvg therefore finds no colour layer, falls back to
the font's monochrome outline and renders the pair as a single black blob;
naming the font explicitly changes nothing, because the format is the problem.
Headless Chrome renders it in colour at the same sizes, and Georgia and
Courier come out indistinguishable from rsvg's. The script needs Google Chrome
on the default macOS path, or `CHROME` set to another binary, and it renders
with a throwaway profile so it never touches the browser's own state.

Two consequences worth knowing before publishing. The emoji artwork baked into
these PNGs is Apple's, which is a licensing question that rsvg's black
silhouette did not raise — an openly licensed set such as Twemoji (CC-BY 4.0)
or Noto Emoji (OFL) would avoid it. And the PNGs now depend on which macOS
version drew them, so a rebuild on a different machine can shift the emoji
artwork even though the database stays byte for byte identical.

## Check these first when the case is next loaded

Three things in this case have never been through the game:

1. **The five-way self join.** `What is your real name` already bets on a
   ten-way one and has not been tried either. If the console refuses it, the
   two-list intersection above still reaches him.
2. **The emoji in `name`.** The artwork is settled: this case renders through
   headless Chrome rather than `rsvg-convert`, so 👉👈 comes out in colour on
   both the preview and the chat log. The case *title* in `config.json` is the
   untested one: the game draws that with its own font, and if it has no emoji
   coverage the title may come out as two empty boxes. Falling back to
   `Vibe Code` costs the case nothing.
3. **TEXT dates.** Every other case here stores a date as an `INTEGER`. The
   intended solution only ever compares one with `=` against a literal, so
   this should be the least of the three, but the sort route leans on a text
   column ordering correctly.

What the case *does* now establish, from the console itself: **there is no
`LIMIT`.** That is why the answer is one row rather than the top of a list.
