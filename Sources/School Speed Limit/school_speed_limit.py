"""
Generates the SQLite database for the custom case "School Speed Limit".

The speed camera outside Lindenhall Primary logs every vehicle that passes it.
The school zone sign restricts the street to 40 km/h during the two arrival and
pick-up windows -- 06:00 to 08:00 and 15:00 to 17:00 -- and leaves the ordinary
60 km/h limit in force the rest of the day. Exactly one vehicle broke the zone
limit inside one of those windows.

Times are whole numbers, written the way the camera prints them: 1500 is 15:00,
801 is 08:01, and 760 is not a time at all. Speeds are whole kilometres per
hour. As in the other three cases, nothing in the database is fractional.

The difficulty lives in the data distribution rather than in any rule engine,
and here it is one trap pointing each way -- the player has to be strict about
the speed and inclusive about the time:

  * eight vehicles pass at exactly 40 inside the windows and are all within the
    limit, so `speed >= 40` accuses nine drivers instead of one;
  * the culprit passes at 15:00 exactly, so `time > 1500` accuses nobody at all
    and the player has to go back and reconsider the window's edge;
  * fourteen vehicles break 40 between the windows, where the limit is 60, so
    merging the two windows into one 06:00-17:00 span accuses eighteen drivers;
  * six more sit just outside the edges -- 05:59, 08:01, 08:30, 14:59, 17:01 and
    17:30 -- so rounding the windows outwards accuses six;
  * `speed > 40` on its own accuses twenty-one, and the windows on their own
    return hundreds of passes.

Every random pass is kept below the zone limit by `compliant_speed()`, which is
what makes all of those counts exact by construction rather than by luck, the
same way `honest_score()` pins the boundary count in `top_of_the_class.py`.

`verify()` asserts all of the above and runs automatically, so the script
refuses to leave an unsolvable database behind.

Run from anywhere:  python3 "Sources/School Speed Limit/school_speed_limit.py"
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

DATABASE_NAME = "school_zone"
DATABASE_PATH = REPO / "School Speed Limit" / DATABASE_NAME # straight into the case folder

SEED = 20261007 # fixed, so a rebuild reproduces the shipped case exactly --
                # the evidence artwork and README quote figures from this data
CULPRIT_NAME = "Delphine Crowhurst"

DRIVER_COUNT = 60
PASSES_PER_DRIVER = 7 # so the row count is fixed by construction and the
                      # camera report can quote it

# The sign outside the school. Both windows are inclusive at both ends, which is
# the whole point of the second trap below.
RESTRICTED = ((600, 800), (1500, 1700))
ZONE_LIMIT = 40
STREET_LIMIT = 60 # what applies between and around the windows

CAMERA_OPEN = 500
CAMERA_CLOSE = 1859

SPEED_MIN = 18
SPEED_MAX = ZONE_LIMIT - 1 # every random pass is within the zone limit, which
                           # is what makes the counts below exact

CULPRIT_TIME = 1500 # the window's own edge, so `time > 1500` finds nobody
CULPRIT_SPEED = 52
CULPRIT_PLATE = "RH 7742" # quoted in the case README, so it is pinned here
                          # rather than drawn at random. Deliberately NOT on any
                          # evidence image -- the plate is the answer.

AT_LIMIT_COUNT = 8 # vehicles doing exactly 40 inside a window: within the limit
# Over the zone limit but outside the windows, where 60 applies. Pinned, because
# the camera report and the README quote these times.
NEAR_EDGE_PASSES = ((559, 47), (801, 58), (830, 51), (1459, 49), (1701, 55), (1730, 57))
MIDDAY_COUNT = 14 # over 40 between the windows, still under the street limit
# Kept clear of WIDENED below, so rounding the windows outwards catches only the
# near-edge passes and that suspect count stays fixed by construction.
MIDDAY_WINDOW = (901, 1359)
MIDDAY_SPEEDS = (44, 58)

MODELS = [
    "Averly Hatchback", "Coleford Estate", "Brayton Pickup", "Dunmere Saloon",
    "Fenwick Van", "Harlow Compact", "Marsden SUV", "Oakfield Coupe",
]
PLATE_LETTERS = "BCDFGHJKLMNPRSTVWXYZ"

# Figures quoted on the evidence artwork. verify() checks them against the
# database, so a rebuild that changes the data fails instead of quietly making
# the artwork lie.
README_PASSES_LOGGED = DRIVER_COUNT * PASSES_PER_DRIVER
ARTWORK_AT_LIMIT = AT_LIMIT_COUNT

# Figures quoted in the case README, each one a wrong query's answer. These are
# fixed by construction, and verify() proves it.
README_AT_OR_OVER_SUSPECTS = 1 + AT_LIMIT_COUNT
README_MERGED_SUSPECTS = 1 + MIDDAY_COUNT + sum(
    1 for time, _ in NEAR_EDGE_PASSES if RESTRICTED[0][0] <= time <= RESTRICTED[-1][1]
)
README_OVER_SUSPECTS = 1 + MIDDAY_COUNT + len(NEAR_EDGE_PASSES)
WIDENED = ((600, 900), (1400, 1800)) # the windows rounded outwards
README_WIDENED_SUSPECTS = 1 + sum(
    1 for time, _ in NEAR_EDGE_PASSES
    if any(start <= time <= end for start, end in WIDENED)
)
# Quoted in the README only. Not fixed by construction the way the counts above
# are -- it falls out of the seeded draw, which is exactly why verify() pins it:
# a rebuild that moves it fails instead of quietly making the README lie.
README_WINDOW_PASSES = 142 # passes inside the windows at any speed

def in_restricted(time: int) -> bool:
    "Whether the sign's 40 limit was in force when the camera took the picture."
    return any(start <= time <= end for start, end in RESTRICTED)

@database_connection(str(DATABASE_PATH))
def create_tables(connection: sqlite3.Connection) -> None:
    driver_rows, vehicle_rows = build_fleet()
    pass_rows = build_passes(vehicle_rows)
    create_drivers_table(connection, driver_rows)
    create_vehicles_table(connection, vehicle_rows)
    create_camera_log_table(connection, pass_rows)
    verify(connection)

def build_fleet() -> Tuple[list, list]:
    """
    One driver per registered vehicle. The culprit sits somewhere in the middle
    of the list rather than at either end.
    Returns a tuple of (drivers, vehicles).
    """
    culprit_id = random.randint(2, DRIVER_COUNT - 1) # never first, never last
    driver_rows = []
    vehicle_rows = []
    taken_names = {CULPRIT_NAME}
    taken_plates = {CULPRIT_PLATE}

    for driver_id in range(1, DRIVER_COUNT + 1):
        is_culprit = driver_id == culprit_id
        driver_rows.append({
            "driver_id": driver_id,
            "name": CULPRIT_NAME if is_culprit else next_name(taken_names),
        })
        vehicle_rows.append({
            "plate": CULPRIT_PLATE if is_culprit else next_plate(taken_plates),
            "driver_id": driver_id,
            "model": random.choice(MODELS),
        })
    return driver_rows, vehicle_rows

def build_passes(vehicle_rows: list) -> list:
    """
    Every pass the camera logged that day. One driver carries the single pass
    that breaks the zone limit inside a window; a handful of others carry the
    passes that punish a wrong query; everyone else is simply driving slowly.
    """
    plates = {row["driver_id"]: row["plate"] for row in vehicle_rows}
    culprit_id = next(
        row["driver_id"] for row in vehicle_rows if row["plate"] == CULPRIT_PLATE
    )

    others = [driver_id for driver_id in plates if driver_id != culprit_id]
    marked = random.sample(others, AT_LIMIT_COUNT + len(NEAR_EDGE_PASSES) + MIDDAY_COUNT)
    at_limit_ids = marked[:AT_LIMIT_COUNT]
    near_edge_ids = marked[AT_LIMIT_COUNT:AT_LIMIT_COUNT + len(NEAR_EDGE_PASSES)]
    midday_ids = marked[AT_LIMIT_COUNT + len(NEAR_EDGE_PASSES):]

    # Each driver's one notable pass, if they have one. Everything else they did
    # that day is within the zone limit.
    notable = {culprit_id: (CULPRIT_TIME, CULPRIT_SPEED)}
    for driver_id in at_limit_ids:
        notable[driver_id] = (restricted_time(), ZONE_LIMIT)
    for driver_id, pinned in zip(near_edge_ids, NEAR_EDGE_PASSES):
        notable[driver_id] = pinned
    for driver_id in midday_ids:
        notable[driver_id] = (random_time(*MIDDAY_WINDOW), random.randint(*MIDDAY_SPEEDS))

    pass_rows = []
    for driver_id, plate in plates.items():
        passes = [notable[driver_id]] if driver_id in notable else []
        while len(passes) < PASSES_PER_DRIVER:
            passes.append((random_time(CAMERA_OPEN, CAMERA_CLOSE), compliant_speed()))
        for time, speed in passes:
            pass_rows.append({"plate": plate, "time": time, "speed": speed})

    # Sorted by the time on the picture, so the offending pass is not
    # conspicuously first in the table.
    pass_rows.sort(key=lambda row: (row["time"], row["plate"]))
    for log_id, row in enumerate(pass_rows, start=1):
        row["log_id"] = log_id
    return pass_rows

def random_time(low: int, high: int) -> int:
    """
    A time the camera could actually print. Times are HHMM, so the minute half
    has to stay under 60 -- 759 is a real time and 760 is not.
    """
    while True:
        time = random.randint(low, high)
        if time % 100 < 60:
            return time

def restricted_time() -> int:
    "A time inside one of the two windows on the sign."
    return random_time(*random.choice(RESTRICTED))

def compliant_speed() -> int:
    """
    A speed within the zone limit. Keeping every random pass below 40 is what
    pins the suspect counts the README and the artwork quote, the same way
    `honest_score()` pins the boundary count in `top_of_the_class.py`.
    """
    return random.randint(SPEED_MIN, SPEED_MAX)

def next_name(taken: set) -> str:
    "A unique driver name, so the arrest is never ambiguous."
    while True:
        first_name, last_name = get_random_name()
        name = f"{first_name} {last_name}"
        if name not in taken:
            taken.add(name)
            return name

def next_plate(taken: set) -> str:
    "A unique plate, in the format the camera prints."
    while True:
        letters = "".join(random.choice(PLATE_LETTERS) for _ in range(2))
        plate = f"{letters} {random.randint(1000, 9999)}"
        if plate not in taken:
            taken.add(plate)
            return plate

def create_drivers_table(connection: sqlite3.Connection, driver_rows: list) -> None:
    create_populate_table(connection, "drivers", {
        "driver_id": "INTEGER",
        "name": "TEXT",
    }, driver_rows)

def create_vehicles_table(connection: sqlite3.Connection, vehicle_rows: list) -> None:
    create_populate_table(connection, "vehicles", {
        "plate": "TEXT",
        "driver_id": "INTEGER",
        "model": "TEXT",
    }, vehicle_rows)

def create_camera_log_table(connection: sqlite3.Connection, pass_rows: list) -> None:
    create_populate_table(connection, "camera_log", {
        "log_id": "INTEGER",
        "plate": "TEXT",
        "time": "INTEGER",
        "speed": "INTEGER",
    }, pass_rows)

PASSES = """
    SELECT d.name  AS name,
           v.plate AS plate,
           c.time  AS time,
           c.speed AS speed
    FROM camera_log c
    JOIN vehicles v ON v.plate = c.plate
    JOIN drivers  d ON d.driver_id = v.driver_id
"""

OVER = f"speed > {ZONE_LIMIT}"
AT_OR_OVER = f"speed >= {ZONE_LIMIT}"

def window_condition(windows=RESTRICTED, lower=">=", upper="<=") -> str:
    """
    The time half of the query, written out one window per branch. `lower` and
    `upper` are the comparisons the player wrote: `>` and `<` are the off-by-one
    that loses the pass sitting on the window's edge.
    """
    return " OR ".join(
        f"(time {lower} {start} AND time {upper} {end})" for start, end in windows
    )

def names_where(connection: sqlite3.Connection, condition: str) -> list:
    "Runs a solution attempt and returns the drivers it accuses."
    query = f"SELECT DISTINCT name FROM ({PASSES}) WHERE {condition} ORDER BY name"
    return [row[0] for row in connection.execute(query)]

def verify(connection: sqlite3.Connection) -> None:
    "Fails loudly rather than leaving an unsolvable case behind."
    solution = f"{OVER} AND ({window_condition()})"
    accused = names_where(connection, solution)
    require(
        accused == [CULPRIT_NAME],
        f"the intended solution should name only {CULPRIT_NAME}, got {accused}",
    )
    offence = connection.execute(f"""
        SELECT name, plate, time, speed FROM ({PASSES}) WHERE {solution}
    """).fetchall()
    require(
        offence == [(CULPRIT_NAME, CULPRIT_PLATE, CULPRIT_TIME, CULPRIT_SPEED)],
        f"the solution should return exactly one pass, got {offence}",
    )

    at_or_over = names_where(connection, f"{AT_OR_OVER} AND ({window_condition()})")
    require(
        len(at_or_over) == README_AT_OR_OVER_SUSPECTS and CULPRIT_NAME in at_or_over,
        f"`speed >= {ZONE_LIMIT}` should accuse {README_AT_OR_OVER_SUSPECTS}"
        f" drivers including the culprit, got {at_or_over}",
    )

    strict = names_where(
        connection, f"{OVER} AND ({window_condition(lower='>', upper='<')})"
    )
    require(
        strict == [],
        f"excluding the windows' edges should accuse nobody, got {strict}",
    )

    merged = names_where(
        connection,
        f"{OVER} AND ({window_condition(((RESTRICTED[0][0], RESTRICTED[-1][1]),))})",
    )
    require(
        len(merged) == README_MERGED_SUSPECTS and CULPRIT_NAME in merged,
        f"merging the windows should accuse {README_MERGED_SUSPECTS} drivers,"
        f" got {len(merged)}",
    )

    widened = names_where(connection, f"{OVER} AND ({window_condition(WIDENED)})")
    require(
        len(widened) == README_WIDENED_SUSPECTS and CULPRIT_NAME in widened,
        f"rounding the windows outwards should accuse {README_WIDENED_SUSPECTS}"
        f" drivers, got {len(widened)}",
    )

    over_anywhere = names_where(connection, OVER)
    require(
        len(over_anywhere) == README_OVER_SUSPECTS and CULPRIT_NAME in over_anywhere,
        f"dropping the time condition should accuse {README_OVER_SUSPECTS} drivers,"
        f" got {len(over_anywhere)}",
    )

    window_passes = count(
        connection, f"SELECT COUNT(*) FROM ({PASSES}) WHERE {window_condition()}"
    )
    require(
        window_passes == README_WINDOW_PASSES,
        f"the README quotes {README_WINDOW_PASSES} passes inside the windows,"
        f" found {window_passes}",
    )

    at_limit = count(connection, f"""
        SELECT COUNT(*) FROM ({PASSES})
        WHERE speed = {ZONE_LIMIT} AND ({window_condition()})
    """)
    require(
        at_limit == ARTWORK_AT_LIMIT,
        f"the artwork quotes {ARTWORK_AT_LIMIT} passes at exactly {ZONE_LIMIT}"
        f" inside the windows, found {at_limit}",
    )
    require(
        count(connection, f"SELECT COUNT(*) FROM camera_log WHERE speed = {ZONE_LIMIT}")
        == ARTWORK_AT_LIMIT,
        f"a pass at exactly {ZONE_LIMIT} fell outside the windows, where it proves"
        " nothing",
    )

    logged = count(connection, "SELECT COUNT(*) FROM camera_log")
    require(
        logged == README_PASSES_LOGGED,
        f"the README quotes {README_PASSES_LOGGED} passes logged, found {logged}",
    )
    require(
        count(connection, f"SELECT COUNT(*) FROM camera_log WHERE speed > {STREET_LIMIT}")
        == 0,
        f"a vehicle broke the {STREET_LIMIT} street limit, so it is a second offence",
    )
    require(
        count(connection, f"""
            SELECT COUNT(*) FROM ({PASSES})
            WHERE name = '{CULPRIT_NAME}' AND {OVER}
        """) == 1,
        "the culprit should break the limit exactly once",
    )

    require(
        count(connection, """
            SELECT COUNT(*) FROM camera_log c
            LEFT JOIN vehicles v ON v.plate = c.plate
            WHERE v.driver_id IS NULL
        """) == 0,
        "a logged pass cannot be joined to a registered vehicle",
    )
    require(
        count(connection, """
            SELECT COUNT(*) FROM vehicles v
            LEFT JOIN drivers d ON d.driver_id = v.driver_id
            WHERE d.name IS NULL
        """) == 0,
        "a vehicle is registered to nobody",
    )
    require(
        count(connection, "SELECT COUNT(DISTINCT name) FROM drivers") == DRIVER_COUNT,
        "driver names are not unique",
    )
    require(
        count(connection, "SELECT COUNT(DISTINCT plate) FROM vehicles") == DRIVER_COUNT,
        "plates are not unique",
    )
    require(
        count(connection, f"""
            SELECT COUNT(*) FROM camera_log
            WHERE time % 100 >= 60 OR time < {CAMERA_OPEN} OR time > {CAMERA_CLOSE}
        """) == 0,
        "a logged time is not a real clock time inside the camera's hours",
    )
    require(
        count(connection, """
            SELECT COUNT(*) FROM camera_log
            WHERE speed <> CAST(speed AS INTEGER) OR speed <= 0
              OR time <> CAST(time AS INTEGER)
        """) == 0,
        "a logged speed or time is not a whole positive number",
    )

    print(f"Wrote {DATABASE_PATH}")
    print(f"Culprit: {CULPRIT_NAME}, plate {CULPRIT_PLATE}, logged at"
          f" {CULPRIT_TIME // 100:02d}:{CULPRIT_TIME % 100:02d} doing {CULPRIT_SPEED}")
    print(f"{DRIVER_COUNT} drivers, {logged} passes logged,"
          f" {window_passes} of them inside the windows")
    print(f"{at_limit} passes sit at exactly {ZONE_LIMIT} inside the windows and are"
          " all within the limit")
    print(f"`speed >= {ZONE_LIMIT}` accuses {len(at_or_over)} drivers;"
          f" `speed > {ZONE_LIMIT}` alone accuses {len(over_anywhere)}")
    print(f"Merging the windows accuses {len(merged)}; rounding them outwards"
          f" accuses {len(widened)}")
    print("Excluding the windows' edges accuses nobody, so the edges are inclusive.")

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
