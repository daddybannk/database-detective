# School Speed Limit

A custom case about the one car that came through the school zone too fast at
the wrong hour, and a camera that records the plate, the time and the speed and
nothing else.

The sign outside Lindenhall Primary restricts the street to 40 km/h during the
two windows on it — **06:00 to 08:00** and **15:00 to 17:00** — and leaves the
ordinary 60 km/h limit in force the rest of the day. Both windows include their
own end times.

Times are whole numbers, written the way the camera prints them: `1500` is
15:00, `801` is 08:01, and `760` is not a time at all. Speeds are whole
kilometers per hour.

## Solution

```sql
SELECT d.name
FROM camera_log c
JOIN vehicles v ON v.plate = c.plate
JOIN drivers  d ON d.driver_id = v.driver_id
WHERE c.speed > 40
  AND ((c.time >= 600 AND c.time <= 800)
    OR (c.time >= 1500 AND c.time <= 1700));
```

`Delphine Crowhurst`, plate `RH 7742`, an Oakfield Coupe logged at 15:00 doing
52 km/h.

`window_condition()` in the generator builds that same time clause, so
`verify()` checks the case with the query a player actually has to type. The
windows are written out as four comparisons rather than with `BETWEEN`, because
the in-game console is only documented to be missing `CASE` and the other three
cases stay inside `>=`, `<=`, `AND` and `OR` as well. `BETWEEN 600 AND 800` is
equivalent if the console accepts it.

Nothing in the database says which hours are restricted — the sign does, the
same way the grading scale in _Top of the Class_ lives on the registrar's wall
and not in a table.

`school_speed_limit.py` seeds its random number generator, so rebuilding
reproduces this exact database; the figures quoted here and on the evidence
artwork stay true.

## What makes it hard

The join is straightforward: every logged pass has one plate, every plate one
owner. The difficulty is one trap pointing each way — the player has to be
**strict about the speed and inclusive about the time**.

- **`speed >= 40` accuses nine drivers.** Eight vehicles pass at exactly 40
  inside the windows, which is within the limit, not over it. `compliant_speed()`
  keeps every random pass below 40, which is what fixes that count at eight and
  lets the camera report quote it.
- **`time > 1500` accuses nobody.** The culprit crosses the camera at 15:00
  exactly, on the window's own edge. A player who excludes the edges gets an
  empty result and has to go back to the sign. She also makes four other passes
  inside the windows that day — 06:05, 07:28, 07:36 and 15:36 — all of them
  under 40, so her offending pass is the only thing that singles her out.
- **Merging the two windows accuses eighteen.** Fourteen vehicles break 40
  between 09:01 and 13:59, where the limit is 60 and they are doing nothing
  wrong. `time >= 600 AND time <= 1700` sweeps all of them up.
- **Rounding the windows outwards accuses six.** Six more over-40 passes sit
  just outside the edges — 05:59, 08:01, 08:30, 14:59, 17:01 and 17:30 — so
  widening to 06:00–09:00 and 14:00–18:00 picks up five of them.
- **Dropping either half is worse.** `speed > 40` on its own accuses
  twenty-one drivers; the windows on their own return 142 passes.

60 drivers, one vehicle each, 7 passes apiece: 420 passes logged and exactly one
of them breaks the limit on the sign.

## Rebuilding

Both commands write into this folder. Run them from the repository root:

```bash
python3 "Sources/School Speed Limit/school_speed_limit.py"   # the database
"Sources/School Speed Limit/build.sh"                        # the artwork (needs rsvg-convert)
```

`school_speed_limit.py` re-checks every count above and refuses to finish if one
breaks, so a regenerated database is always solvable.
