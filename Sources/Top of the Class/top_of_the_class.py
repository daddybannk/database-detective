"""
Generates the SQLite database for the custom case "Top of the Class".

A student went into the registrar's system and raised their own grade, but the
exam scores live in a different table and they never touched those. Every
transcript row has exactly one exam score beside it; exactly one of them
disagrees with the mark it was awarded for.

The grading scale is a staircase: 80+ is an A, 70+ a B, 60+ a C, 50+ a D, and
anything below 50 is an F. Scores are whole numbers in an INTEGER column -- as
in `one_dollar.py`, nothing in the database is fractional.

The game's SQL console has no `CASE` expression, so the scale has to be written
out band by band with AND and OR; `mismatch_condition()` below builds exactly
the query a player has to type, and that is what `verify()` checks with.

As in the other two cases, the difficulty lives in the data distribution rather
than in any rule engine:
  * the forged grade is a B, not an A, so the shortcut `grade = 'A' AND score <
    80` finds nobody and the player has to compare every band;
  * twelve scores land exactly on a cut-off (three each at 80, 70, 60 and 50)
    and are graded correctly, so a player who writes `score > 80` instead of
    `score >= 80` accuses twelve innocent students;
  * random scores stay off those four values, which is what fixes that count at
    twelve and lets the evidence artwork quote it.

`verify()` asserts all of the above and runs automatically, so the script
refuses to leave an unsolvable database behind.

Run from anywhere:  python3 "Sources/Top of the Class/top_of_the_class.py"
"""
import random
import sqlite3
import sys
from pathlib import Path
from typing import Tuple

# db_utils and its name lists come from the upstream workshop kit, which is
# vendored as a submodule and deliberately left untouched -- so reach into it
# rather than copying it out.
REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "dbd-workshop" / "Scripts"))

from db_utils import create_populate_table, database_connection, get_random_name

DATABASE_NAME = "university"
DATABASE_PATH = REPO / "Top of the Class" / DATABASE_NAME # written straight into the case folder

SEED = 20261006 # fixed, so a rebuild reproduces the shipped case exactly --
                # the evidence artwork and README quote figures from this data
CULPRIT_NAME = "Royce Danbury"

STUDENT_COUNT = 90
COURSES_PER_STUDENT = 5 # out of six on offer, so the row count is fixed by
                        # construction and the artwork can quote it

# score needed, grade awarded. Ordered from the top down, which is the order the
# bands have to be written out in.
SCALE = ((80, "A"), (70, "B"), (60, "C"), (50, "D"))
FAIL_GRADE = "F"

SCORE_MIN = 31
SCORE_MAX = 98
CUTOFFS = tuple(score for score, _ in SCALE)
BOUNDARY_PER_CUTOFF = 3 # students sitting exactly on each cut-off, graded right

CULPRIT_SCORE = 58 # a D by the scale on the wall
CULPRIT_GRADE = "B" # what the transcript says instead
CULPRIT_COURSE = "Software Engineering" # named on the camera still, so it is
                                        # pinned here rather than drawn at random

COURSES = [
    "Introduction to Databases",
    "Discrete Mathematics",
    "Operating Systems",
    "Computer Networks",
    "Software Engineering",
    "Statistics for Computing",
]

# Figures quoted on the evidence artwork. verify() checks them against the
# database, so a rebuild that changes the data fails instead of quietly making
# the artwork lie.
ARTWORK_GRADES_ISSUED = STUDENT_COUNT * COURSES_PER_STUDENT
ARTWORK_BOUNDARY_SCORES = BOUNDARY_PER_CUTOFF * len(CUTOFFS)

def grade_for(score: int) -> str:
    "The grade the scale on the registrar's wall gives a score."
    for needed, grade in SCALE:
        if score >= needed:
            return grade
    return FAIL_GRADE

@database_connection(str(DATABASE_PATH))
def create_tables(connection: sqlite3.Connection) -> None:
    course_rows = build_courses()
    student_rows, score_rows, transcript_rows = build_results(course_rows)
    create_students_table(connection, student_rows)
    create_courses_table(connection, course_rows)
    create_exam_scores_table(connection, score_rows)
    create_transcripts_table(connection, transcript_rows)
    verify(connection)

def build_courses() -> list:
    "One row per course the department ran this term."
    return [
        {"course_id": index, "title": title}
        for index, title in enumerate(COURSES, start=1)
    ]

def build_results(course_rows: list) -> Tuple[list, list, list]:
    """
    Builds the student, exam score and transcript rows together, because a grade
    only means anything next to the score it was awarded for.
    Returns a tuple of (students, exam_scores, transcripts).
    """
    student_rows = []
    score_rows = []
    transcript_rows = []

    culprit_id = random.randint(2, STUDENT_COUNT - 1) # never first, never last
    course_ids = [course["course_id"] for course in course_rows]
    culprit_course_id = course_id_for(course_rows, CULPRIT_COURSE)

    taken_names = {CULPRIT_NAME}
    for student_id in range(1, STUDENT_COUNT + 1):
        is_culprit = student_id == culprit_id
        student_rows.append({
            "student_id": student_id,
            "name": CULPRIT_NAME if is_culprit else next_name(taken_names),
        })
        enrolled = sorted(random.sample(course_ids, COURSES_PER_STUDENT))
        if is_culprit:
            enrolled = with_course(enrolled, culprit_course_id)
        forged_course = culprit_course_id if is_culprit else None
        for course_id in enrolled:
            if course_id == forged_course:
                score, grade = CULPRIT_SCORE, CULPRIT_GRADE
            else:
                score = honest_score()
                grade = grade_for(score)
            score_rows.append({
                "student_id": student_id,
                "course_id": course_id,
                "score": score,
            })
            transcript_rows.append({
                "student_id": student_id,
                "course_id": course_id,
                "grade": grade,
            })

    sit_on_cutoffs(score_rows, transcript_rows, culprit_id)
    return student_rows, score_rows, transcript_rows

def course_id_for(course_rows: list, title: str) -> int:
    "The id of the course the camera still names."
    for course in course_rows:
        if course["title"] == title:
            return course["course_id"]
    raise AssertionError(f"{title} is not one of the courses on offer")

def with_course(enrolled: list, course_id: int) -> list:
    "The same timetable, guaranteed to include one particular course."
    if course_id in enrolled:
        return enrolled
    return sorted(enrolled[1:] + [course_id])

def honest_score() -> int:
    """
    A score that is not sitting on a cut-off. Keeping the randoms off those four
    values is what pins the number of boundary cases at twelve, the same way
    `matches_plate()` in `where.py` keeps random houses off the culprit's plate.
    """
    while True:
        score = random.randint(SCORE_MIN, SCORE_MAX)
        if score not in CUTOFFS:
            return score

def sit_on_cutoffs(score_rows: list, transcript_rows: list, culprit_id: int) -> None:
    """
    Moves a few students onto each cut-off exactly, with the right grade. These
    are the decoys: `score > 80` instead of `score >= 80` accuses all of them.
    """
    candidates = [
        index for index, row in enumerate(score_rows)
        if row["student_id"] != culprit_id
    ]
    chosen = random.sample(candidates, BOUNDARY_PER_CUTOFF * len(CUTOFFS))
    for cutoff, indexes in zip(CUTOFFS, chunk(chosen, BOUNDARY_PER_CUTOFF)):
        for index in indexes:
            score_rows[index]["score"] = cutoff
            transcript_rows[index]["grade"] = grade_for(cutoff)

def chunk(items: list, size: int):
    "Walks a list in fixed-size pieces."
    for start in range(0, len(items), size):
        yield items[start:start + size]

def next_name(taken: set) -> str:
    "A unique student name, so the arrest is never ambiguous."
    while True:
        first_name, last_name = get_random_name()
        name = f"{first_name} {last_name}"
        if name not in taken:
            taken.add(name)
            return name

def create_students_table(connection: sqlite3.Connection, student_rows: list) -> None:
    create_populate_table(connection, "students", {
        "student_id": "INTEGER",
        "name": "TEXT",
    }, student_rows)

def create_courses_table(connection: sqlite3.Connection, course_rows: list) -> None:
    create_populate_table(connection, "courses", {
        "course_id": "INTEGER",
        "title": "TEXT",
    }, course_rows)

def create_exam_scores_table(connection: sqlite3.Connection, score_rows: list) -> None:
    create_populate_table(connection, "exam_scores", {
        "student_id": "INTEGER",
        "course_id": "INTEGER",
        "score": "INTEGER",
    }, score_rows)

def create_transcripts_table(connection: sqlite3.Connection, transcript_rows: list) -> None:
    create_populate_table(connection, "transcripts", {
        "student_id": "INTEGER",
        "course_id": "INTEGER",
        "grade": "TEXT",
    }, transcript_rows)

RESULTS = """
    SELECT s.name AS name,
           c.title AS course,
           e.score AS score,
           t.grade AS grade
    FROM transcripts t
    JOIN exam_scores e ON e.student_id = t.student_id AND e.course_id = t.course_id
    JOIN students    s ON s.student_id = t.student_id
    JOIN courses     c ON c.course_id = t.course_id
"""

# Without a CASE expression a band is written as a pair of comparisons, so each
# comparison needs its opposite. `>` instead of `>=` is the off-by-one a player
# makes at the cut-offs, and it carries through to `<=`.
OPPOSITE = {">=": "<", ">": "<="}

def outside_band(index: int, operator: str) -> str:
    """
    The test that catches a grade awarded to the wrong score. `index` walks SCALE
    from the top down and runs one past its end for the failing grade;
    `operator` is the comparison the player wrote.
    """
    below = OPPOSITE[operator]
    if index == 0:
        return f"score {below} {SCALE[0][0]}" # nothing sits above an A
    if index == len(SCALE):
        return f"score {operator} {SCALE[-1][0]}" # nothing sits below an F
    return f"(score {below} {SCALE[index][0]} OR score {operator} {SCALE[index - 1][0]})"

def mismatch_condition(operator: str) -> str:
    """
    The query a player has to write without a CASE expression: one band per
    grade, ORed together, each catching a score that does not belong with it.
    """
    grades = [grade for _, grade in SCALE] + [FAIL_GRADE]
    return " OR ".join(
        f"(grade = '{grade}' AND {outside_band(index, operator)})"
        for index, grade in enumerate(grades)
    )

def names_where(connection: sqlite3.Connection, condition: str) -> list:
    "Runs a solution attempt and returns the students it accuses."
    query = f"SELECT DISTINCT name FROM ({RESULTS}) WHERE {condition} ORDER BY name"
    return [row[0] for row in connection.execute(query)]

def verify(connection: sqlite3.Connection) -> None:
    "Fails loudly rather than leaving an unsolvable case behind."
    solution = names_where(connection, mismatch_condition(">="))
    require(
        solution == [CULPRIT_NAME],
        f"the intended solution should name only {CULPRIT_NAME}, got {solution}",
    )

    off_by_one = names_where(connection, mismatch_condition(">"))
    require(
        len(off_by_one) > 1,
        f"`score > 80` should accuse a crowd, got {off_by_one}",
    )
    require(
        CULPRIT_NAME in off_by_one,
        "the strict comparison does not even accuse the culprit, so the data is wrong",
    )

    straight_a = names_where(connection, f"grade = 'A' AND score < {SCALE[0][0]}")
    require(
        straight_a == [],
        f"the A shortcut should find nobody, got {straight_a}",
    )

    forged = connection.execute(f"""
        SELECT course, score, grade FROM ({RESULTS}) WHERE name = '{CULPRIT_NAME}'
          AND ({mismatch_condition('>=')})
    """).fetchall()
    require(
        forged == [(CULPRIT_COURSE, CULPRIT_SCORE, CULPRIT_GRADE)],
        f"the culprit should have exactly one forged row, got {forged}",
    )

    boundary = count(connection, f"""
        SELECT COUNT(*) FROM exam_scores WHERE score IN {CUTOFFS}
    """)
    require(
        boundary == ARTWORK_BOUNDARY_SCORES,
        f"the artwork quotes {ARTWORK_BOUNDARY_SCORES} scores on a cut-off, found {boundary}",
    )
    require(
        count(connection, f"""
            SELECT COUNT(*) FROM ({RESULTS})
            WHERE score IN {CUTOFFS} AND ({mismatch_condition('>=')})
        """) == 0,
        "a student sitting on a cut-off is graded wrongly, so they are a second suspect",
    )

    issued = count(connection, "SELECT COUNT(*) FROM transcripts")
    require(
        issued == ARTWORK_GRADES_ISSUED,
        f"the artwork quotes {ARTWORK_GRADES_ISSUED} grades issued, found {issued}",
    )
    require(
        count(connection, "SELECT COUNT(*) FROM exam_scores") == issued,
        "a transcript row has no exam score beside it, or the other way round",
    )
    require(
        count(connection, """
            SELECT COUNT(*) FROM transcripts t
            LEFT JOIN exam_scores e
              ON e.student_id = t.student_id AND e.course_id = t.course_id
            WHERE e.score IS NULL
        """) == 0,
        "a transcript row cannot be joined to an exam score",
    )

    require(
        count(connection, "SELECT COUNT(DISTINCT name) FROM students") == STUDENT_COUNT,
        "student names are not unique",
    )
    require(
        count(connection, f"""
            SELECT COUNT(*) FROM exam_scores
            WHERE score <> CAST(score AS INTEGER) OR score < 0 OR score > 100
        """) == 0,
        "a score is not a whole number between 0 and 100",
    )
    grades = tuple(grade for _, grade in SCALE) + (FAIL_GRADE,)
    require(
        count(connection, f"SELECT COUNT(*) FROM transcripts WHERE grade NOT IN {grades}") == 0,
        f"a transcript carries a grade outside {grades}",
    )

    print(f"Wrote {DATABASE_PATH}")
    print(f"Culprit: {CULPRIT_NAME}, scored {CULPRIT_SCORE} in {CULPRIT_COURSE}"
          f" and recorded a {CULPRIT_GRADE}")
    print(f"{STUDENT_COUNT} students, {len(COURSES)} courses, {issued} grades issued")
    print(f"{boundary} scores sit exactly on a cut-off and are all graded correctly")
    print(f"`score >` instead of `score >=` accuses {len(off_by_one)} students")
    print("The A shortcut finds nobody, so every band has to be compared.")
    print("No CASE anywhere: the scale is written out with AND and OR.")

def count(connection: sqlite3.Connection, query: str):
    row = connection.execute(query).fetchone()
    return row[0] if row else None

def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)

def main() -> None:
    # CREATE TABLE IF NOT EXISTS plus INSERT would append to an existing file,
    # so start from scratch on every run.
    DATABASE_PATH.unlink(missing_ok=True)
    random.seed(SEED)
    create_tables()

if __name__ == "__main__":
    main()
