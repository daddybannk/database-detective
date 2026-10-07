# Step Bros

A custom case about the walker who rode part of a twenty-kilometre endurance
walk.

Every walker carries a pedometer that a marshal reads at each of the eight
checkpoints, so `pedometer` holds one row per walker per stage: the steps taken,
against the metres that stage is long. Both are whole numbers, and the case is
solved by comparing them directly.

A walking stride never reaches a metre, so a stage whose metres beat its steps
did not happen on foot.

## Solution

```sql
SELECT w.name
FROM pedometer p
JOIN walkers w ON w.walker_id = p.walker_id
JOIN stages  s ON s.stage_id  = p.stage_id
WHERE s.distance > p.steps;
```

`Corbin Halstead`, who logged 1,480 steps across the 3,300 m of Ashdown Ridge
-- a stride of 2.2 metres.

`step_bros.py` seeds its random number generator, so rebuilding reproduces this
exact database -- the figures quoted here and on the evidence artwork stay true.

## What makes it hard

One trap pointing each way: the player has to look at a single stage, and has to
resist both the total and the average.

- **Totalling a walker's stages accuses nobody.** Halstead walked the other seven
  stages honestly, so `SUM(distance) > SUM(steps)` returns no rows at all, and
  `>=` returns none either. The cheat only exists on one line.
- **`distance >= steps` accuses eight.** Seven walkers have one stage each at
  exactly a metre a stride, which is walking and is cleared on the rules card.
- **The average points at the wrong person.** Fifteen walkers average fewer
  steps per metre than Halstead does, five of them because they genuinely
  stride 90 cm or more; the lowest average in the race belongs to one of those.
  Sorting by steps per metre arrests an innocent walker.
- **Six walkers retired part way and four never started.** A walker's row count
  says nothing about them, and the four who never started have no rows at all.

`honest_steps()` never lets a stride reach a metre, so every stage but the
culprit's is strictly above the line and all of those counts are fixed by
construction rather than by the draw.

## Workshop description

Paste into the Steam Workshop description field. No spoilers: it names the
traps without naming the walker.

> The Lindenhall Twenty is a twenty-kilometre endurance walk in eight stages.
> Every walker carries a pedometer, and a marshal reads it at each checkpoint,
> so the log holds one line per walker per stage: the steps they took, against
> the metres that stage is long.
>
> A walking stride never reaches a metre. One walker did not walk all of it.
>
> Three traps sit in the way. Totalling a walker's stages forgives the one they
> rode. The lowest steps-per-metre average in the race belongs to someone who
> is simply tall. And seven walkers covered a stage at exactly a metre a
> stride, which is walking, and was cleared.
>
> Three tables, JOIN and WHERE. Everything in the database is a whole number.

## Rebuilding

Both commands write into this folder. Run them from the repository root:

```bash
python3 "Sources/Step Bros/step_bros.py"   # the database
"Sources/Step Bros/build.sh"               # the artwork (needs rsvg-convert)
```

`step_bros.py` re-checks every property above and refuses to finish if one
breaks, so a regenerated database is always solvable.
