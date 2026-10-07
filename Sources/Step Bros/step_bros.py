"""
Generates the SQLite database for the custom case "Step Bros".

The Lindenhall Twenty is a twenty-kilometre endurance walk in eight stages. Every
walker carries a pedometer that a marshal reads at each stage, so the
database holds one row per walker per stage: the steps they took, against the
metres that stage is long.

A walking stride is somewhere between half a metre and a metre. Nobody covers
more ground than they take steps, so a stage where the metres beat the steps did
not happen on foot. Exactly one walker has such a stage.

Steps and metres are both whole numbers in INTEGER columns and the puzzle
compares them directly, so there is no division anywhere -- which is the point.
A steps-per-metre average is a fraction, and `one_dollar.py` already records
what fractions do to a case in this game.

The difficulty is one trap pointing each way, so the player has to look at a
single stage and resist both the total and the average:

  * the culprit rode the 3,300 m Ashdown Ridge stage and logged 1,480 steps, but
    walked the other seven stages honestly, so their totals come out ordinary and
    `SUM(distance) > SUM(steps)` per walker accuses nobody at all;
  * seven other walkers have one stage each at exactly a metre a stride, which is
    walking, so `distance >= steps` accuses eight;
  * five walkers stride 90 cm or more the whole way, so the lowest steps-per-
    metre average belongs to one of them and not to the culprit, whose average
    sits mid-field;
  * six walkers retired part way and four never started, so a walker's row
    count says nothing about them.

`honest_steps()` keeps every other stage strictly above the line -- a stride is
never allowed to reach a metre by accident -- which is what makes those counts
exact by construction rather than by luck, the same way `compliant_speed()`
pins them in `school_speed_limit.py`.

`verify()` asserts all of the above and runs automatically, so the script
refuses to leave an unsolvable database behind.

Run from anywhere:  python3 "Sources/Step Bros/step_bros.py"
"""
import random
import sqlite3
import sys
from pathlib import Path
from typing import List

# db_utils and its name lists come from the upstream workshop kit, which is
# vendored as a submodule and deliberately left untouched -- so reach into it
# rather than copying it out.
REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "dbd-workshop" / "Scripts"))

from db_utils import create_populate_table, database_connection, get_random_name

DATABASE_NAME = "long_walk"
DATABASE_PATH = REPO / "Step Bros" / DATABASE_NAME # straight into the case folder

SEED = 20261008 # fixed, so a rebuild reproduces the shipped case exactly --
                # the evidence artwork and README quote figures from this data
CULPRIT_NAME = "Corbin Halstead"

WALKER_COUNT = 50

# The course, in the order the stages come. Twenty kilometres exactly,
# which the rules board quotes.
STAGES = (
    ("Mill Bridge", 2400),
    ("Hollow Lane", 3100),
    ("Beacon Rise", 1800),
    ("Fenn Crossing", 2750),
    ("Ashdown Ridge", 3300),
    ("Water Meadow", 2100),
    ("Quarry Track", 2600),
    ("Lindenhall Green", 1950),
)
STAGE_COUNT = len(STAGES)
COURSE_METRES = sum(metres for _, metres in STAGES)

# Stride in whole centimetres. The ceiling is 89, never 100, so every honest stage
# has strictly more steps than metres and the suspect counts below are fixed by
# construction instead of by the draw.
STRIDE_MIN_CM = 58
STRIDE_MAX_CM = 89
STRIDE_WOBBLE_CM = 3 # how much a walker's stride varies stage to stage
METRE_CM = 100

CULPRIT_STAGE = "Ashdown Ridge"
CULPRIT_STEPS = 1480 # against 3,300 m: a 2.2 m stride, which is a car
CULPRIT_STRIDE_CM = 72 # what they walk when they are walking

AT_LIMIT_COUNT = 7 # walkers with one stage at exactly a metre a stride: walking,
                   # so `distance >= steps` accuses them as well
LONG_STRIDE_COUNT = 5 # walkers who stride 90 cm or more all the way: the lowest
                      # steps-per-metre average belongs to one of them
LONG_STRIDE_CM = (90, 97)

RETIRED_COUNT = 6 # walkers who stopped at a stage and have no rows after it
NO_START_COUNT = 4 # walkers who have no rows at all

# Figures quoted on the evidence artwork, which verify() checks against the
# database so a rebuild that changes the data fails instead of quietly making
# the artwork lie.
ARTWORK_COURSE_METRES = COURSE_METRES # the course card totals them
README_AT_LIMIT = AT_LIMIT_COUNT # quoted in the README and in caseHints, but no
                                 # longer on the artwork: the rules card says
                                 # "at least as many steps", which settles the
                                 # boundary without naming a count

# Figures quoted in the case README, each one a wrong query's answer, all fixed
# by construction. verify() proves every one of them.
README_AT_OR_OVER_SUSPECTS = 1 + AT_LIMIT_COUNT
README_RETIRED = RETIRED_COUNT
README_NO_START = NO_START_COUNT
# Walkers whose average stride beats the culprit's, so the average points well
# away from them. Not fixed by construction the way the counts above are -- it
# falls out of the seeded draw, which is exactly why verify() pins it: a rebuild
# that moves it fails instead of quietly making the README lie.
README_FASTER_AVERAGES = 15

@database_connection(str(DATABASE_PATH))
def create_tables(connection: sqlite3.Connection) -> None:
    walker_rows = build_walkers()
    stage_rows = build_stages()
    record_rows = build_records(walker_rows, stage_rows)
    create_walkers_table(connection, walker_rows)
    create_stages_table(connection, stage_rows)
    create_pedometer_table(connection, record_rows)
    verify(connection)

def build_walkers() -> List[dict]:
    """
    Everyone on the start list. The culprit sits somewhere in the middle of it
    rather than at either end.
    """
    culprit_id = random.randint(2, WALKER_COUNT - 1) # never first, never last
    taken_names = {CULPRIT_NAME}
    return [
        {
            "walker_id": walker_id,
            "name": CULPRIT_NAME if walker_id == culprit_id else next_name(taken_names),
        }
        for walker_id in range(1, WALKER_COUNT + 1)
    ]

def build_stages() -> List[dict]:
    "The eight stages of the course, in the order they are walked."
    return [
        {"stage_id": stage_id, "name": name, "distance": metres}
        for stage_id, (name, metres) in enumerate(STAGES, start=1)
    ]

def build_records(walker_rows: List[dict], stage_rows: List[dict]) -> List[dict]:
    """
    One pedometer reading per walker per stage they finished. The culprit's ride
    is a single stage; everybody else's stages are all walked, including the seven
    that are walked at exactly a metre a stride.
    """
    culprit_id = next(
        row["walker_id"] for row in walker_rows if row["name"] == CULPRIT_NAME
    )
    others = [row["walker_id"] for row in walker_rows if row["walker_id"] != culprit_id]
    marked = random.sample(
        others, NO_START_COUNT + RETIRED_COUNT + AT_LIMIT_COUNT + LONG_STRIDE_COUNT
    )
    no_start = set(marked[:NO_START_COUNT])
    retired = marked[NO_START_COUNT:NO_START_COUNT + RETIRED_COUNT]
    rest = marked[NO_START_COUNT + RETIRED_COUNT:]
    at_limit = rest[:AT_LIMIT_COUNT]
    long_stride = rest[AT_LIMIT_COUNT:]

    # Which stage each of the seven walked at exactly a metre a stride.
    at_limit_stage = {
        walker_id: random.choice(stage_rows)["stage_id"] for walker_id in at_limit
    }
    # Where each retirement happened: they have rows up to and including this stage.
    last_stage = {
        walker_id: random.randint(2, STAGE_COUNT - 2) for walker_id in retired
    }
    culprit_stage_id = next(
        row["stage_id"] for row in stage_rows if row["name"] == CULPRIT_STAGE
    )

    record_rows = []
    for row in walker_rows:
        walker_id = row["walker_id"]
        if walker_id in no_start:
            continue
        if walker_id == culprit_id:
            stride = CULPRIT_STRIDE_CM
        elif walker_id in long_stride:
            stride = random.randint(*LONG_STRIDE_CM)
        else:
            stride = random.randint(STRIDE_MIN_CM, STRIDE_MAX_CM)

        for stage in stage_rows:
            if walker_id in last_stage and stage["stage_id"] > last_stage[walker_id]:
                break
            metres = stage["distance"]
            if walker_id == culprit_id and stage["stage_id"] == culprit_stage_id:
                steps = CULPRIT_STEPS
            elif at_limit_stage.get(walker_id) == stage["stage_id"]:
                steps = metres # exactly a metre a stride, which is still walking
            else:
                steps = honest_steps(metres, stride)
            record_rows.append({
                "walker_id": walker_id,
                "stage_id": stage["stage_id"],
                "steps": steps,
            })

    # Sorted by stage, the way the marshals read the pedometers, so the culprit's
    # row is not conspicuously placed.
    record_rows.sort(key=lambda row: (row["stage_id"], row["walker_id"]))
    for record_id, row in enumerate(record_rows, start=1):
        row["record_id"] = record_id
    return record_rows

def honest_steps(metres: int, stride_cm: int) -> int:
    """
    The steps a stage takes at this stride, give or take the walker's wobble. The
    stride can never reach a metre, so an honest stage always has strictly more
    steps than metres -- which is what fixes every suspect count below.
    """
    wobble = random.randint(-STRIDE_WOBBLE_CM, STRIDE_WOBBLE_CM)
    stride = min(max(stride_cm + wobble, STRIDE_MIN_CM), STRIDE_MAX_CM)
    steps = -(-metres * METRE_CM // stride) # round up, so a part step still counts
    assert steps > metres
    return steps

def next_name(taken: set) -> str:
    "A unique walker name, so the arrest is never ambiguous."
    while True:
        first_name, last_name = get_random_name()
        name = f"{first_name} {last_name}"
        if name not in taken:
            taken.add(name)
            return name

def create_walkers_table(connection: sqlite3.Connection, walker_rows: List[dict]) -> None:
    create_populate_table(connection, "walkers", {
        "walker_id": "INTEGER",
        "name": "TEXT",
    }, walker_rows)

def create_stages_table(connection: sqlite3.Connection, stage_rows: List[dict]) -> None:
    create_populate_table(connection, "stages", {
        "stage_id": "INTEGER",
        "name": "TEXT",
        "distance": "INTEGER",
    }, stage_rows)

def create_pedometer_table(connection: sqlite3.Connection, record_rows: List[dict]) -> None:
    create_populate_table(connection, "pedometer", {
        "record_id": "INTEGER",
        "walker_id": "INTEGER",
        "stage_id": "INTEGER",
        "steps": "INTEGER",
    }, record_rows)

READINGS = """
    SELECT w.name         AS name,
           s.name       AS stage,
           s.distance   AS distance,
           p.steps        AS steps
    FROM pedometer p
    JOIN walkers w ON w.walker_id = p.walker_id
    JOIN stages  s ON s.stage_id  = p.stage_id
"""

def names_where(connection: sqlite3.Connection, condition: str) -> List[str]:
    "Runs a solution attempt and returns the walkers it accuses."
    query = f"SELECT DISTINCT name FROM ({READINGS}) WHERE {condition} ORDER BY name"
    return [row[0] for row in connection.execute(query)]

def names_having(connection: sqlite3.Connection, having: str) -> List[str]:
    "The same, for an attempt that totals a walker's stages before comparing."
    query = f"""
        SELECT name FROM ({READINGS}) GROUP BY name HAVING {having} ORDER BY name
    """
    return [row[0] for row in connection.execute(query)]

def verify(connection: sqlite3.Connection) -> None:
    "Fails loudly rather than leaving an unsolvable case behind."
    accused = names_where(connection, "distance > steps")
    require(
        accused == [CULPRIT_NAME],
        f"the intended solution should name only {CULPRIT_NAME}, got {accused}",
    )
    offence = connection.execute(f"""
        SELECT name, stage, distance, steps FROM ({READINGS}) WHERE distance > steps
    """).fetchall()
    require(
        offence == [(CULPRIT_NAME, CULPRIT_STAGE, dict(STAGES)[CULPRIT_STAGE], CULPRIT_STEPS)],
        f"the solution should return exactly one stage, got {offence}",
    )

    at_or_over = names_where(connection, "distance >= steps")
    require(
        len(at_or_over) == README_AT_OR_OVER_SUSPECTS and CULPRIT_NAME in at_or_over,
        f"`distance >= steps` should accuse {README_AT_OR_OVER_SUSPECTS} walkers"
        f" including the culprit, got {at_or_over}",
    )

    totalled = names_having(connection, "SUM(distance) > SUM(steps)")
    require(
        totalled == [],
        f"totalling a walker's stages should accuse nobody, got {totalled}",
    )
    totalled_at_or_over = names_having(connection, "SUM(distance) >= SUM(steps)")
    require(
        totalled_at_or_over == [],
        f"totalling with `>=` should accuse nobody either, got {totalled_at_or_over}",
    )

    # The average the player is tempted by: fewest steps per metre walked.
    ranking = connection.execute(f"""
        SELECT name, SUM(steps) * 1.0 / SUM(distance) AS steps_per_metre
        FROM ({READINGS}) GROUP BY name ORDER BY steps_per_metre
    """).fetchall()
    require(
        ranking[0][0] != CULPRIT_NAME,
        "the lowest steps-per-metre average belongs to the culprit, so the"
        " average alone would solve the case",
    )
    beating = [name for name, _ in ranking[:ranking.index(
        next(row for row in ranking if row[0] == CULPRIT_NAME)
    )]]
    require(
        len(beating) == README_FASTER_AVERAGES,
        f"{README_FASTER_AVERAGES} walkers should average fewer steps per metre"
        f" than the culprit, got {len(beating)}",
    )

    at_limit = count(connection, f"""
        SELECT COUNT(*) FROM ({READINGS}) WHERE distance = steps
    """)
    require(
        at_limit == README_AT_LIMIT,
        f"the README quotes {README_AT_LIMIT} stages walked at exactly a metre a"
        f" stride, found {at_limit}",
    )
    require(
        count(connection, f"""
            SELECT COUNT(*) FROM ({READINGS})
            WHERE name = '{CULPRIT_NAME}' AND distance >= steps
        """) == 1,
        "the culprit should have exactly one stage they did not walk",
    )
    require(
        count(connection, f"""
            SELECT COUNT(*) FROM ({READINGS}) WHERE name = '{CULPRIT_NAME}'
        """) == STAGE_COUNT,
        "the culprit should have a reading for every stage, having finished",
    )

    course = count(connection, "SELECT SUM(distance) FROM stages")
    require(
        course == ARTWORK_COURSE_METRES,
        f"the artwork quotes {ARTWORK_COURSE_METRES} metres of course, found {course}",
    )
    require(
        count(connection, "SELECT COUNT(*) FROM stages") == STAGE_COUNT,
        f"the course should have {STAGE_COUNT} stages",
    )

    no_start = count(connection, """
        SELECT COUNT(*) FROM walkers w
        LEFT JOIN pedometer p ON p.walker_id = w.walker_id
        WHERE p.record_id IS NULL
    """)
    require(
        no_start == README_NO_START,
        f"the README quotes {README_NO_START} walkers who never started, found"
        f" {no_start}",
    )
    retired = count(connection, f"""
        SELECT COUNT(*) FROM (
            SELECT walker_id FROM pedometer GROUP BY walker_id
            HAVING COUNT(*) < {STAGE_COUNT}
        )
    """)
    require(
        retired == README_RETIRED,
        f"the README quotes {README_RETIRED} walkers who retired, found {retired}",
    )

    require(
        count(connection, """
            SELECT COUNT(*) FROM pedometer p
            LEFT JOIN walkers w ON w.walker_id = p.walker_id
            WHERE w.name IS NULL
        """) == 0,
        "a pedometer reading belongs to nobody on the start list",
    )
    require(
        count(connection, """
            SELECT COUNT(*) FROM pedometer p
            LEFT JOIN stages s ON s.stage_id = p.stage_id
            WHERE s.name IS NULL
        """) == 0,
        "a pedometer reading belongs to a stage that is not on the course",
    )
    require(
        count(connection, "SELECT COUNT(DISTINCT name) FROM walkers") == WALKER_COUNT,
        "walker names are not unique",
    )
    require(
        count(connection, """
            SELECT COUNT(*) FROM pedometer
            WHERE steps <= 0 OR steps <> CAST(steps AS INTEGER)
        """) == 0,
        "a pedometer reading is not a whole positive number of steps",
    )
    require(
        count(connection, """
            SELECT COUNT(*) FROM (
                SELECT walker_id, stage_id FROM pedometer
                GROUP BY walker_id, stage_id HAVING COUNT(*) > 1
            )
        """) == 0,
        "a walker has two readings for the same stage",
    )

    readings = count(connection, "SELECT COUNT(*) FROM pedometer")
    print(f"Wrote {DATABASE_PATH}")
    print(f"Culprit: {CULPRIT_NAME}, {CULPRIT_STEPS} steps across"
          f" {dict(STAGES)[CULPRIT_STAGE]} m of {CULPRIT_STAGE}")
    print(f"{WALKER_COUNT} walkers, {STAGE_COUNT} stages, {course} m of course,"
          f" {readings} pedometer readings")
    print(f"`distance >= steps` accuses {len(at_or_over)}; totalling the stages"
          " accuses nobody")
    print(f"{len(beating)} walkers average fewer steps per metre than the culprit,"
          f" the lowest being {ranking[0][0]}")
    print(f"{retired} walkers retired, {no_start} never started")

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
