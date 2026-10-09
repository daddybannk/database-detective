# What is your real name?

A custom case about a man who has renamed himself every year for ten years,
and a registry that keeps no record of who anybody used to be.

Allison Burgers emptied a treasury and left the capital in the autumn of 2016.
A caller recognised him in a bus queue this morning, under a name nine changes
newer than the one on the warrant.

`residents` holds one row per person under the name they answer to now — the
clerk types each new name straight over the old one. `name_changes` holds the
old name, the new name and the year it was stamped. Neither carries a person
number, so names are the only thread between them.

Today is 8 October 2026 — the date on the transcript is what tells a player
so, and it is the only thing on the evidence that does. The log runs 2014 to
2026 and years are plain integers.

## Solution

```sql
SELECT c10.new_name
FROM name_changes c1
JOIN name_changes c2  ON c2.old_name  = c1.new_name  AND c2.year  = 2018
JOIN name_changes c3  ON c3.old_name  = c2.new_name  AND c3.year  = 2019
JOIN name_changes c4  ON c4.old_name  = c3.new_name  AND c4.year  = 2020
JOIN name_changes c5  ON c5.old_name  = c4.new_name  AND c5.year  = 2021
JOIN name_changes c6  ON c6.old_name  = c5.new_name  AND c6.year  = 2022
JOIN name_changes c7  ON c7.old_name  = c6.new_name  AND c7.year  = 2023
JOIN name_changes c8  ON c8.old_name  = c7.new_name  AND c8.year  = 2024
JOIN name_changes c9  ON c9.old_name  = c8.new_name  AND c9.year  = 2025
JOIN name_changes c10 ON c10.old_name = c9.new_name  AND c10.year = 2026
WHERE c1.old_name = 'Allison Burgers' AND c1.year = 2017;
```

`Max Imumoccupancy`, resident 688263, a night porter in Kettleford.

The chain, in full:

| Year | Name it gave him | | Year | Name it gave him |
| ---: | :--- | --- | ---: | :--- |
| 2017 | Way Owt | | 2022 | Dee Tourahead |
| 2018 | Ladiz Washroom | | 2023 | Fyre Exitonly |
| 2019 | Emplyes Mustwashhands | | 2024 | Kip Clearofdoors |
| 2020 | Noah Diving | | 2025 | Max Wellhouse |
| 2021 | Mynd Thegap | | 2026 | Max Imumoccupancy |

He takes each name off whatever sign he has been stood next to, which the
caller says outright. 2025 is the year he tried to go straight, which is why
the last change alters only the surname.

**Ten separate one-table queries walk the same chain**, and that matters more
here than it does in the other cases: nothing in this repository has yet
established that the in-game console will take a ten-way self join. If it
balks, the case is still solvable, one query at a time:

```sql
SELECT new_name FROM name_changes WHERE old_name = 'Allison Burgers' AND year = 2017;
SELECT new_name FROM name_changes WHERE old_name = 'Way Owt'         AND year = 2018;
-- ... and so on to 2026
```

The years are written out as literals rather than `c1.year + 1` for the same
reason: arithmetic inside an expression has not been tried in that console
either. Dropping the `year` from any step breaks the chain, because three of
the names on it were taken by somebody else as well.

`what_is_your_real_name.py` seeds its random number generator, so rebuilding
reproduces this exact database — the figures quoted here and on the evidence
artwork stay true.

## What makes it hard

The registry cannot be asked the question. `WHERE name = 'Allison Burgers'`
returns nothing, and so does every intermediate name on the chain, because a
name somebody has given up only exists in the log. No evidence card says so —
the schema and that one empty result say it between them, which is why the
case ships with two pieces of evidence rather than four. Everything after that
is a matter of not stepping off the chain:

- **The first step has two rows.** A protester legally took the dictator's
  name in 2019 to shame the ministry into looking for him, and dropped it
  again in 2021. `WHERE old_name = 'Allison Burgers'` returns both his 2021
  change and the culprit's 2017 one, and nothing on the evidence explains why
  — the warrant's "every year since 2017" is the only thing that picks between
  them, and it is enough, because the protester never renamed himself two
  years running. The protester has renamed himself twice
  since — 2023, then 2026, never two years running — and his chain ends at
  `Dunn Otdisturb`, a barber in Thurnby. Starting on the wrong row
  arrests an innocent man rather than returning nothing, which is the whole
  point of putting him there.
- **Assuming the last change is the one stamped in 2026 arrests
  `Owt Tolunch`.** The culprit's own name after 2024, `Kip Clearofdoors`, was
  copied off the same door by somebody else, and that man left it in 2026 —
  the year a player expects the final change to be in. The culprit left it in
  2025. This is the sharpest trap in the case and the last one a player meets.
- **Two more names on the chain are shared the same way.** `Ladiz Washroom`
  has an onward change in 2021 as well as the culprit's in 2019, and
  `Noah Diving` one in 2023 as well as his in 2021. Each wrong branch ends at
  a living resident. The chain only stays single-file if every step insists on
  the very next year.
- **Asking the question structurally accuses two.** Strip the starting name
  out of the join and ask which chain runs through all ten years, and a sign
  painter's apprentice comes back alongside the culprit: he renamed himself
  every year too, from `Harold Stennick`, and is now `Gon Fishing`. The wanted
  file's name is the only thing that separates them.
- **The chain-end shortcut accuses twenty-four.** `WHERE year = 2026 AND
  new_name NOT IN (SELECT old_name FROM name_changes)` finds everybody whose
  last change was this year. The culprit is one of them and the query cannot
  say which.
- **Picking the daft name out of the column by eye accuses one of thirteen.**
  Renaming yourself after a sign is a fad in this city, which the caller says
  he started early and the log bears out. Thirteen residents
  answer to one and forty-five sign names appear in the log. With no
  description to check a name against, the registry gives a player nothing to
  narrow them by.
- **Stopping at 2025 leaves nine people called Max.** The second-to-last name
  is an ordinary one, and a player who reads it as the answer has nine
  residents to choose between.
- **Nothing else in the data singles him out.** He filed his ten changes at
  five different counters, so grouping the log by office finds no cluster; his
  rows are neither the first nor the last in it; and `change_no` climbs with
  the year and with nothing else.

626 residents and 627 changes stamped between 2014 and 2026.

## Workshop description

> He emptied the treasury and he was gone before the building had finished
> burning. That was ten years ago this autumn. This morning a woman who served
> under him stood behind him in a bus queue, shook his hand, and was given
> another name.
>
> He has changed his name every year he has been here. Ten years, ten names,
> and the civil registry keeps the old one in a different book from the new
> one and no person number in either — Records has never issued one. The
> warrant on the wall is nine names out of date.
>
> You have the name he ran with and the year he started. Everything between
> that and the man on the bus is one row at a time.
>
> Take the wrong row early and you will arrest a protester. Take it late and
> you will arrest somebody who reads a lot of doors.

## Rebuilding

Both commands write into this folder. Run them from the repository root:

```bash
python3 "Sources/What is your real name/what_is_your_real_name.py"  # the database
"Sources/What is your real name/build.sh"                           # the artwork
```

`what_is_your_real_name.py` re-checks every property above and refuses to
finish if one breaks, so a regenerated database is always solvable.
