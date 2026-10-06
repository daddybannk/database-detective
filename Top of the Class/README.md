# Top of the Class

A custom case about the student who edited their own grade in the registrar's
system and forgot that the exam scores live in a different table.

Scores are whole numbers from 0 to 100, and grades come from one scale: 80+ is
an A, 70+ a B, 60+ a C, 50+ a D, and anything below 50 is an F. Nothing in the
database is fractional.

## Solution

The game's SQL console has no `CASE` expression, so the scale is written out one
band per grade:

```sql
SELECT s.name
FROM transcripts t
JOIN exam_scores e ON e.student_id = t.student_id AND e.course_id = t.course_id
JOIN students    s ON s.student_id = t.student_id
WHERE (t.grade = 'A' AND e.score < 80)
   OR (t.grade = 'B' AND (e.score < 70 OR e.score >= 80))
   OR (t.grade = 'C' AND (e.score < 60 OR e.score >= 70))
   OR (t.grade = 'D' AND (e.score < 50 OR e.score >= 60))
   OR (t.grade = 'F' AND e.score >= 50);
```

`mismatch_condition()` in the generator builds this same string from `SCALE`, so
`verify()` checks the case with the query a player actually has to type. One
band on its own is enough once the player guesses the right one — `t.grade = 'B'
AND e.score < 70` returns the culprit alone — but nothing points at B in
advance.

`Royce Danbury`, who scored 58 in Software Engineering — a D — and has a B on
the transcript for it.

The camera still names that course, so `WHERE c.title = 'Software Engineering'`
narrows the search to 83 rows; `CULPRIT_COURSE` in the generator pins it, so the
evidence cannot drift away from the data.

`top_of_the_class.py` seeds its random number generator, so rebuilding
reproduces this exact database; the figures quoted here and on the evidence
artwork stay true.

## What makes it hard

Every transcript row has exactly one exam score beside it, so the join itself
is straightforward. The difficulty is in the data:

- **The forged grade is a B, not an A.** `grade = 'A' AND score < 80` finds
  nobody at all, so the player cannot skim the top band and stop. The culprit
  also holds an honest B elsewhere (74 in Computer Networks), which is what
  keeps the forged row from standing out on sight.
- **Twelve scores land exactly on a cut-off** — three each at 80, 70, 60 and 50
  — and all twelve are graded correctly. A player who writes `score > 80`
  instead of `score >= 80` accuses thirteen students instead of one. Random
  scores are kept off those four values by `honest_score()`, which is what
  fixes that count at twelve and lets the camera still's caption quote it.
- **Leaving the D band out is worse than useless.** A chain that jumps from C
  to F condemns everyone who scored between 50 and 59: 51 names come back
  instead of one.

90 students, 6 courses, 5 courses each: 450 grades issued and exactly one of
them disagrees with its score.

## Rebuilding

Both commands write into this folder. Run them from the repository root:

```bash
python3 "Sources/Top of the Class/top_of_the_class.py"   # the database
"Sources/Top of the Class/build.sh"                      # the artwork (needs rsvg-convert)
```

`top_of_the_class.py` re-checks every property above and refuses to finish if
one breaks, so a regenerated database is always solvable.
