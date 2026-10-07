"""
Generates the SQLite database for the custom case "Which Bob?".

A letter arrived at the station this morning. It promises to deal with
everybody in the building and it is signed with a first name: Bob. Everyone
remembers the man -- a serving officer until the force let him go -- and
nobody remembers his surname. The only thing anybody is sure of is that it
happened last month.

Three hundred officers on the roster are called Bob, so the name alone names
nobody. The roster is no help on its own either: the station has never deleted
a row from it, so the man who was dismissed is still listed exactly like the
299 Bobs who came in to work today. The only record of who still turns up is
the fingerprint scanner on the staff door.

And that is the trap. Today is 7 October; he was dismissed on 30 September. He
has no scan this month at all -- not a late one, not an early one, none. Every
query that reaches for his most recent scan *this month* returns an empty
table, because what identifies him is an absence. The intended solution asks
each Bob when he was last seen and keeps the one whose answer is still in
September:

    SELECT o.first_name, o.last_name
    FROM officers o
    JOIN fingerprint_scans s ON s.badge_id = o.badge_id
    WHERE o.first_name = 'Bob'
    GROUP BY o.badge_id
    HAVING MAX(s.date) < 20261001;

The difficulty lives in the data distribution rather than in any rule engine,
and every shortcut here points somewhere else:

  * asking only about this month's scans accuses nobody, which is what forces
    a player to look for the absence instead of for a row, whether they reach
    for `HAVING MAX(date)`, a set difference, `NOT IN` or a `LEFT JOIN`;
  * forgetting to filter the first name accuses eight, because seven other
    officers left last month too;
  * `LIKE 'Bob%'` accuses two, because one of the forty Bobbys on the roster
    is among those seven;
  * being strict about the 30th -- `MAX(date) < 20260930` -- accuses nobody
    named Bob, because the culprit's last shift was that day;
  * "the Bob nobody has seen for longest, of those still scanning" is four
    innocent men whose last scan is 1 October: they left or went on leave
    *this* month, which is not what the station remembers;
  * the Bob with the fewest scans in the log is innocent too -- he was sworn
    in at the end of September -- and the culprit's own count sits mid-pack;
  * looking at September alone accuses all 300, because every Bob worked some
    part of last month, the culprit included.

Every one of those counts is fixed by construction rather than by the draw.
`duty_days()` forces each serving officer a scan on or after 2 October and
each officer a scan in September, so the only Bob missing from this month is
the culprit and the only Bobs whose log ends on 1 October are the four meant
to. That is the same trick `compliant_speed()` plays in `school_speed_limit.py`.

Dates are YYYYMMDD and times HHMM, both in INTEGER columns, for the reason
`spy_everywhere.py` and `school_speed_limit.py` give: a player reads them off
the evidence without converting anything. `scan_time()` can only produce a
real clock time, and `verify()` rechecks every stamped date by rebuilding it
with `datetime.date`.

`verify()` asserts all of the above and runs automatically, so the script
refuses to leave an unsolvable database behind.

Run from anywhere:  python3 "Sources/Which Bob/which_bob.py"
"""
import random
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

# db_utils and its name lists come from the upstream workshop kit, which is
# vendored as a submodule and deliberately left untouched -- so reach into it
# rather than copying it out.
REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "dbd-workshop" / "Scripts"))

from db_utils import create_populate_table, database_connection, get_random_name

DATABASE_NAME = "station_access"
DATABASE_PATH = REPO / "Which Bob" / DATABASE_NAME # straight into the case folder

SEED = 20261007 # fixed, so a rebuild reproduces the shipped case exactly --
                # the evidence artwork and README quote figures from this data

CULPRIT_FIRST = "Bob"
CULPRIT_LAST = "Leeswagger"
CULPRIT_NAME = f"{CULPRIT_FIRST} {CULPRIT_LAST}"

# The letter arrived today. The scanner log is archived at the turn of each
# month, so the terminal holds this month and last month -- which is exactly
# the span the station's memory ("they sacked him last month") points across.
TODAY = date(2026, 10, 7)
LOG_START = date(2026, 9, 1)
MONTH_START = date(2026, 10, 1)
LAST_MONTH_END = date(2026, 9, 30) # the culprit's last shift, and the day the
                                   # force let him go
DAYS = [LOG_START + timedelta(days=offset)
        for offset in range((TODAY - LOG_START).days + 1)]

# Three hundred Bobs is what makes the first name useless, and the forty
# Bobbys are what makes `LIKE 'Bob%'` useless as well.
FIRST_NAME = "Bob"
NEAR_MISS_NAME = "Bobby"
BOB_COUNT = 300
NEAR_MISS_COUNT = 40
OTHER_COUNT = 180
OFFICER_COUNT = BOB_COUNT + NEAR_MISS_COUNT + OTHER_COUNT

# Badge and scan numbers. Neither carries information -- a badge number says
# nothing about when its holder was sworn in, a scan number nothing beyond the
# order of the log -- so sorting by either teaches a player nothing.
BADGE_DIGITS = 5
SCAN_DIGITS = 10

RANKS = ("Officer", "Officer", "Officer", "Senior Officer", "Corporal",
         "Sergeant", "Detective", "Lieutenant")
DIVISIONS = ("Patrol", "Traffic", "Records", "Dispatch", "Evidence",
             "Custom Crimes", "Community Liaison")
DOORS = ("Staff entrance", "Rear gate", "Locker corridor", "Vehicle bay",
         "Evidence lockup")

# A duty block is a shift's start window; a scan lands somewhere inside it.
# (first hour, first minute, last hour, last minute)
DUTY_BLOCKS = ((6, 0, 9, 0), (14, 0, 16, 30), (22, 0, 23, 30))
NIGHT_BLOCK = 2       # the culprit's own, pinned rather than drawn: the letter
                      # says he gave the station nine years of nights, and
                      # verify() holds the database to it
OFF_BLOCK_RATE = 0.12 # shifts somebody covered outside their usual block

# How much of the log window an officer actually works. Low enough to keep the
# log browsable; nothing in the puzzle turns on the frequency.
SHIFT_RATE = (0.22, 0.38)

# The parts officers play. Everyone not named below is still serving, which
# duty_days() guarantees by forcing them a scan on or after 2 October.
GONE_OTHER_COUNT = 6   # officers with ordinary first names who also left last month
GONE_NEAR_MISS_COUNT = 1 # ... and one of the Bobbys, which is the LIKE trap
GONE_WINDOW = (date(2026, 9, 22), date(2026, 9, 29)) # their last shift, all of
                                                     # them before the 30th
EDGE_BOB_COUNT = 4     # Bobs whose log ends on 1 October: gone, or on leave,
                       # but gone *this* month
LATE_JOIN_DAY = date(2026, 9, 29) # the Bob sworn in at the end of last month,
                                  # who has the fewest scans in the log
CULPRIT_RATE = 0.30 # pinned rather than drawn, and chosen so that the culprit's
                    # total lands in the middle of the Bobs' scan counts rather
                    # than at either end of them, where sorting by how often
                    # somebody turned up would find him. verify() holds it
                    # there, so a rebuild that moves it fails

NO_OCTOBER_COUNT = GONE_OTHER_COUNT + GONE_NEAR_MISS_COUNT + 1
NEAR_MISS_ACCUSED = GONE_NEAR_MISS_COUNT + 1
STRICT_30TH_ACCUSED = GONE_OTHER_COUNT + GONE_NEAR_MISS_COUNT

# Surnames that are not in the workshop's name list, handed to ordinary Bobs so
# that "Leeswagger" is not the one odd name in a column of three hundred. A
# player who picks the strange one out by eye arrests somebody innocent.
UNUSUAL_SURNAMES = ("Ravenstoke", "Quillfeather", "Marrowbone", "Pemberlane",
                    "Finchwhistle", "Crowhurst", "Hollinrake", "Stourbeck")

# Counts that fall out of the seeded draw rather than the construction, pinned
# here so a rebuild that moves one fails instead of quietly making the README
# and the artwork lie.
README_SCAN_ROWS = 5773
README_CULPRIT_SCANS = 12
README_FEWER_SCANS = 161
README_MORE_SCANS = 97
README_LATE_JOINER_SCANS = 2
README_BUSIEST_BOB_SCANS = 21
# The culprit's own row and his last shift, quoted in the case README.
README_CULPRIT_BADGE = 53271
README_CULPRIT_RANK = "Sergeant"
README_CULPRIT_DIVISION = "Traffic"
README_CULPRIT_LAST_TIME = 2227

@database_connection(str(DATABASE_PATH))
def create_tables(connection: sqlite3.Connection) -> None:
    officer_rows, plan = build_officers()
    scan_rows = build_scans(officer_rows, plan)
    create_officers_table(connection, officer_rows)
    create_scans_table(connection, scan_rows)
    verify(connection)

def build_officers() -> Tuple[List[dict], Dict[int, dict]]:
    """
    Every officer on the roster and the part each one plays. The roster has no
    column saying who still works here -- that is the whole point of the case,
    so the part an officer plays lives in the returned plan and reaches the
    database only as the shifts they did or did not turn up for.

    Returns the rows, ordered by badge number, and {badge_id: duty plan}.
    """
    taken_surnames = {CULPRIT_LAST, *UNUSUAL_SURNAMES}
    bob_surnames = [CULPRIT_LAST, *UNUSUAL_SURNAMES]
    bob_surnames += unique_surnames(BOB_COUNT - len(bob_surnames), taken_surnames)

    # The culprit first, so the parts below are handed out among the others.
    bobs = [{"first_name": FIRST_NAME, "last_name": surname}
            for surname in bob_surnames]
    culprit, others = bobs[0], bobs[1:]
    random.shuffle(others)
    edge = others[:EDGE_BOB_COUNT]
    late_joiner = others[EDGE_BOB_COUNT]

    near_misses = [{"first_name": NEAR_MISS_NAME, "last_name": surname}
                   for surname in unique_surnames(NEAR_MISS_COUNT, set())]
    gone_near_miss = random.sample(near_misses, GONE_NEAR_MISS_COUNT)

    rest = [{"first_name": first_name, "last_name": last_name}
            for first_name, last_name in unique_names(OTHER_COUNT)]
    gone_rest = random.sample(rest, GONE_OTHER_COUNT)

    plan_by_person = {id(person): {"first_day": LOG_START, "last_day": TODAY,
                                   "rate": random.uniform(*SHIFT_RATE),
                                   "serving": True, "block": None}
                      for person in bobs + near_misses + rest}
    plan_by_person[id(culprit)].update(last_day=LAST_MONTH_END, serving=False,
                                       rate=CULPRIT_RATE, block=NIGHT_BLOCK)
    for person in edge:
        plan_by_person[id(person)].update(last_day=MONTH_START, serving=False)
    plan_by_person[id(late_joiner)].update(first_day=LATE_JOIN_DAY)
    for person in gone_near_miss + gone_rest:
        plan_by_person[id(person)].update(last_day=last_shift(), serving=False)

    roster = bobs + near_misses + rest
    random.shuffle(roster)
    # The culprit should be neither the first nor the last Bob a player scrolls
    # past, however they sort the roster.
    middle = range(OFFICER_COUNT // 5, OFFICER_COUNT - OFFICER_COUNT // 5)
    here, there = roster.index(culprit), random.choice(middle)
    roster[here], roster[there] = roster[there], roster[here]

    badges = unique_ids(OFFICER_COUNT, BADGE_DIGITS)
    officer_rows = []
    plan = {}
    for badge_id, person in zip(badges, roster):
        officer_rows.append({
            "badge_id": badge_id,
            "first_name": person["first_name"],
            "last_name": person["last_name"],
            "rank": random.choice(RANKS),
            "division": random.choice(DIVISIONS),
        })
        plan[badge_id] = plan_by_person[id(person)]
    return officer_rows, plan

def last_shift() -> date:
    "The last day worked by an officer who was let go along with the culprit."
    first_day, last_day = GONE_WINDOW
    return first_day + timedelta(days=random.randint(0, (last_day - first_day).days))

def unique_surnames(count: int, taken: set) -> List[str]:
    "`count` distinct surnames from the workshop's name list."
    surnames = []
    while len(surnames) < count:
        _, last_name = get_random_name()
        if last_name not in taken:
            taken.add(last_name)
            surnames.append(last_name)
    return surnames

def unique_names(count: int) -> List[Tuple[str, str]]:
    """
    `count` distinct full names for the officers who are not part of the
    puzzle. Bob and Bobby are rejected here so the two counts the case turns
    on stay exactly what the constants say.
    """
    names = []
    taken = {CULPRIT_NAME}
    while len(names) < count:
        first_name, last_name = get_random_name()
        full_name = f"{first_name} {last_name}"
        if first_name in (FIRST_NAME, NEAR_MISS_NAME) or full_name in taken:
            continue
        taken.add(full_name)
        names.append((first_name, last_name))
    return names

def unique_ids(count: int, digits: int) -> List[int]:
    "`count` distinct numbers of exactly `digits` digits, in ascending order."
    return sorted(random.sample(range(10 ** (digits - 1), 10 ** digits), count))

def build_scans(officer_rows: List[dict], plan: Dict[int, dict]) -> List[dict]:
    """
    The scanner log, in the order the door recorded it. Scan numbers are handed
    out along that order, so the log reads like a log.
    """
    rows = []
    for officer in officer_rows:
        badge_id = officer["badge_id"]
        duty = plan[badge_id]
        # A pinned block is a shift the officer never strays from, which is how
        # a claim the evidence makes about him survives a rebuild.
        block = random.randrange(len(DUTY_BLOCKS)) if duty["block"] is None \
                else duty["block"]
        for day in duty_days(duty):
            rows.append({
                "badge_id": badge_id,
                "date": stamp(day),
                "time": scan_time(block, strict=duty["block"] is not None),
                "door": random.choice(DOORS),
            })
    rows.sort(key=lambda row: (row["date"], row["time"], row["badge_id"]))
    for scan_id, row in zip(unique_ids(len(rows), SCAN_DIGITS), rows):
        row["scan_id"] = scan_id
    return rows

def duty_days(duty: dict) -> List[date]:
    """
    The days one officer put a finger on the scanner.

    The three forced days are what fix every suspect count in verify() by
    construction instead of by the draw: an officer still serving is always
    seen on or after 2 October, so the only Bob missing from this month is the
    culprit and the only Bobs whose log ends on 1 October are the four meant
    to; everybody is seen in September, so September alone accuses all 300; and
    an officer who left is always seen on their last day, so their last scan is
    that day and not whichever earlier one the draw happened to keep.
    """
    window = [day for day in DAYS
              if duty["first_day"] <= day <= duty["last_day"]]
    days = {day for day in window if random.random() < duty["rate"]}

    september = [day for day in window if day <= LAST_MONTH_END]
    if not any(day <= LAST_MONTH_END for day in days):
        days.add(random.choice(september))
    if duty["serving"]:
        recent = [day for day in window if day > MONTH_START]
        if not any(day > MONTH_START for day in days):
            days.add(random.choice(recent))
    else:
        days.add(duty["last_day"])
    return sorted(days)

def scan_time(block: int, strict: bool = False) -> int:
    "A real clock time inside a duty block, as HHMM."
    if not strict and random.random() < OFF_BLOCK_RATE:
        block = random.randrange(len(DUTY_BLOCKS))
    first_hour, first_minute, last_hour, last_minute = DUTY_BLOCKS[block]
    minutes = random.randint(first_hour * 60 + first_minute,
                             last_hour * 60 + last_minute)
    return (minutes // 60) * 100 + minutes % 60

def stamp(day: date) -> int:
    "A date as the scanner prints it: 20260930 is 30 September 2026."
    return day.year * 10000 + day.month * 100 + day.day

def create_officers_table(connection: sqlite3.Connection,
                          officer_rows: List[dict]) -> None:
    create_populate_table(connection, "officers", {
        "badge_id": "INTEGER",
        "first_name": "TEXT",
        "last_name": "TEXT",
        "rank": "TEXT",
        "division": "TEXT",
    }, officer_rows)

def create_scans_table(connection: sqlite3.Connection, rows: List[dict]) -> None:
    create_populate_table(connection, "fingerprint_scans", {
        "scan_id": "INTEGER",
        "badge_id": "INTEGER",
        "date": "INTEGER",
        "time": "INTEGER",
        "door": "TEXT",
    }, rows)

def names_having(connection: sqlite3.Connection, where: str, having: str) -> List[str]:
    "Runs a solution attempt and returns the officers it accuses."
    query = f"""
        SELECT o.first_name || ' ' || o.last_name AS name
        FROM officers o
        JOIN fingerprint_scans s ON s.badge_id = o.badge_id
        WHERE {where}
        GROUP BY o.badge_id, o.first_name, o.last_name
        HAVING {having}
        ORDER BY name
    """
    return [row[0] for row in connection.execute(query)]

def ranking(connection: sqlite3.Connection, order: str, limit: int = 5) -> List[str]:
    "The Bobs a shortcut puts at the top of its ranking."
    query = f"""
        SELECT o.first_name || ' ' || o.last_name AS name
        FROM officers o
        JOIN fingerprint_scans s ON s.badge_id = o.badge_id
        WHERE o.first_name = '{FIRST_NAME}'
        GROUP BY o.badge_id, o.first_name, o.last_name
        ORDER BY {order}, name
        LIMIT {limit}
    """
    return [row[0] for row in connection.execute(query)]

def verify(connection: sqlite3.Connection) -> None:
    """
    Re-checks every property the case depends on, against the same constants
    the data was built from, and raises rather than leave an unsolvable case
    behind. Changing a count above and re-running is therefore safe.
    """
    this_month = stamp(MONTH_START)
    bob = f"o.first_name = '{FIRST_NAME}'"

    # The roster. The first name names nobody, and neither does the prefix.
    require(count(connection, "SELECT COUNT(*) FROM officers") == OFFICER_COUNT,
            "the roster is not the size the evidence says")
    require(
        count(connection, f"""
            SELECT COUNT(*) FROM officers WHERE first_name = '{FIRST_NAME}'
        """) == BOB_COUNT,
        f"there are not {BOB_COUNT} officers called {FIRST_NAME}",
    )
    require(
        count(connection, f"""
            SELECT COUNT(*) FROM officers WHERE first_name = '{NEAR_MISS_NAME}'
        """) == NEAR_MISS_COUNT,
        f"there are not {NEAR_MISS_COUNT} officers called {NEAR_MISS_NAME}",
    )
    require(
        count(connection, f"""
            SELECT COUNT(*) FROM officers WHERE first_name LIKE '{FIRST_NAME}%'
        """) == BOB_COUNT + NEAR_MISS_COUNT,
        "an unexpected first name starts with Bob",
    )
    require(
        count(connection, "SELECT COUNT(*) FROM officers WHERE "
                          "first_name LIKE '% %' OR last_name LIKE '% %'") == 0,
        "a name has a space in it, so first_name || ' ' || last_name is"
        " ambiguous",
    )

    # The solution, exactly as the case README prints it.
    accused = names_having(connection, bob, f"MAX(s.date) < {this_month}")
    require(accused == [CULPRIT_NAME],
            f"the intended query accuses {accused} rather than {CULPRIT_NAME}")
    require(
        count(connection, f"""
            SELECT COUNT(*) FROM officers
            WHERE first_name = '{FIRST_NAME}' AND badge_id NOT IN (
                SELECT badge_id FROM fingerprint_scans WHERE date >= {this_month})
        """) == 1,
        "the NOT IN form of the solution does not name exactly one officer",
    )
    require(
        count(connection, f"""
            SELECT COUNT(*) FROM (
                SELECT DISTINCT badge_id FROM fingerprint_scans
                WHERE date < {this_month}
                EXCEPT
                SELECT DISTINCT badge_id FROM fingerprint_scans
                WHERE date >= {this_month}) AS r
            JOIN officers o ON o.badge_id = r.badge_id
            WHERE o.first_name = '{FIRST_NAME}'
        """) == 1,
        "the set difference form of the solution does not name exactly one"
        " officer",
    )

    # The trap the case is built on: this month holds no trace of him at all.
    require(
        count(connection, f"""
            SELECT COUNT(*) FROM fingerprint_scans s
            JOIN officers o ON o.badge_id = s.badge_id
            WHERE o.first_name || ' ' || o.last_name = '{CULPRIT_NAME}'
              AND s.date >= {this_month}
        """) == 0,
        "the culprit scanned in this month, so asking about this month works",
    )
    require(
        names_having(connection, f"{bob} AND s.date >= {this_month}", "1=1")
        == names_having(connection, bob, f"MAX(s.date) >= {this_month}"),
        "this month's scans do not account for every Bob but the culprit",
    )
    require(
        count(connection, f"""
            SELECT MAX(s.date) FROM fingerprint_scans s
            JOIN officers o ON o.badge_id = s.badge_id
            WHERE o.first_name || ' ' || o.last_name = '{CULPRIT_NAME}'
        """) == stamp(LAST_MONTH_END),
        "the culprit's last scan is not his last day on the force",
    )

    # The man himself, as the case README introduces him.
    require(
        count(connection, f"""
            SELECT COUNT(*) FROM officers
            WHERE first_name || ' ' || last_name = '{CULPRIT_NAME}'
              AND badge_id = {README_CULPRIT_BADGE}
              AND rank = '{README_CULPRIT_RANK}'
              AND division = '{README_CULPRIT_DIVISION}'
        """) == 1,
        f"{CULPRIT_NAME} is no longer badge {README_CULPRIT_BADGE},"
        f" {README_CULPRIT_RANK} in {README_CULPRIT_DIVISION}",
    )
    require(
        count(connection, f"""
            SELECT time FROM fingerprint_scans s
            JOIN officers o ON o.badge_id = s.badge_id
            WHERE o.first_name || ' ' || o.last_name = '{CULPRIT_NAME}'
            ORDER BY s.date DESC, s.time DESC LIMIT 1
        """) == README_CULPRIT_LAST_TIME,
        f"the culprit's last shift no longer starts at {README_CULPRIT_LAST_TIME}",
    )

    # The letter's one claim about the man: nine years of nights.
    first_hour, first_minute, last_hour, last_minute = DUTY_BLOCKS[NIGHT_BLOCK]
    require(
        count(connection, f"""
            SELECT COUNT(*) FROM fingerprint_scans s
            JOIN officers o ON o.badge_id = s.badge_id
            WHERE o.first_name || ' ' || o.last_name = '{CULPRIT_NAME}'
              AND (s.time < {first_hour * 100 + first_minute}
                OR s.time > {last_hour * 100 + last_minute})
        """) == 0,
        "the culprit worked a shift that is not a night, which the letter"
        " claims he never did",
    )

    # Forgetting the first name, or taking it as a prefix.
    everyone = names_having(connection, "1=1", f"MAX(s.date) < {this_month}")
    require(
        len(everyone) == NO_OCTOBER_COUNT and CULPRIT_NAME in everyone,
        f"dropping the name filter does not accuse exactly {NO_OCTOBER_COUNT}",
    )
    prefix = names_having(connection, f"o.first_name LIKE '{FIRST_NAME}%'",
                          f"MAX(s.date) < {this_month}")
    require(
        len(prefix) == NEAR_MISS_ACCUSED and CULPRIT_NAME in prefix,
        f"LIKE '{FIRST_NAME}%' does not accuse exactly {NEAR_MISS_ACCUSED}",
    )

    # Being strict about the 30th loses him, and being loose about the turn of
    # the month picks up four innocent men instead.
    require(
        names_having(connection, bob, f"MAX(s.date) < {stamp(LAST_MONTH_END)}") == [],
        "a query strict about the 30th still finds the culprit",
    )
    require(
        len(names_having(connection, "1=1",
                         f"MAX(s.date) < {stamp(LAST_MONTH_END)}")
            ) == STRICT_30TH_ACCUSED,
        f"being strict about the 30th does not accuse {STRICT_30TH_ACCUSED}",
    )
    edge = names_having(connection, bob, f"MAX(s.date) = {this_month}")
    require(
        len(edge) == EDGE_BOB_COUNT and CULPRIT_NAME not in edge,
        f"the Bobs last seen on 1 October are not {EDGE_BOB_COUNT} innocent men",
    )
    require(
        ranking(connection, "MAX(s.date) ASC", EDGE_BOB_COUNT + 1)[0] == CULPRIT_NAME,
        "the culprit is not the Bob last seen longest ago overall",
    )

    # Every Bob worked some part of last month, so September alone accuses 300.
    require(
        count(connection, f"""
            SELECT COUNT(DISTINCT o.badge_id) FROM officers o
            JOIN fingerprint_scans s ON s.badge_id = o.badge_id
            WHERE o.first_name = '{FIRST_NAME}'
              AND s.date BETWEEN {stamp(LOG_START)} AND {stamp(LAST_MONTH_END)}
        """) == BOB_COUNT,
        "some Bob has no scan in last month, so September alone narrows it",
    )
    require(
        len(names_having(connection, bob, f"MAX(s.date) >= {this_month}")
            ) == BOB_COUNT - 1,
        "this month does not account for 299 Bobs",
    )

    # Counting scans arrests the wrong man at either end of the ranking.
    fewest = ranking(connection, "COUNT(*) ASC", 1)
    busiest = ranking(connection, "COUNT(*) DESC", 1)
    require(CULPRIT_NAME not in fewest,
            "the Bob with the fewest scans is the culprit")
    require(CULPRIT_NAME not in busiest,
            "the Bob with the most scans is the culprit")
    thinnest = count(connection, f"""
        SELECT MIN(scans) FROM (
            SELECT COUNT(*) AS scans FROM officers o
            JOIN fingerprint_scans s ON s.badge_id = o.badge_id
            WHERE o.first_name = '{FIRST_NAME}' GROUP BY o.badge_id)
    """)
    thickest = count(connection, f"""
        SELECT MAX(scans) FROM (
            SELECT COUNT(*) AS scans FROM officers o
            JOIN fingerprint_scans s ON s.badge_id = o.badge_id
            WHERE o.first_name = '{FIRST_NAME}' GROUP BY o.badge_id)
    """)
    require(
        thinnest == README_LATE_JOINER_SCANS and thickest == README_BUSIEST_BOB_SCANS,
        f"the Bobs' scan counts run {thinnest} to {thickest}, not"
        f" {README_LATE_JOINER_SCANS} to {README_BUSIEST_BOB_SCANS}",
    )
    culprit_scans = count(connection, f"""
        SELECT COUNT(*) FROM fingerprint_scans s
        JOIN officers o ON o.badge_id = s.badge_id
        WHERE o.first_name || ' ' || o.last_name = '{CULPRIT_NAME}'
    """)
    require(culprit_scans == README_CULPRIT_SCANS,
            f"the culprit has {culprit_scans} scans, not {README_CULPRIT_SCANS}")
    fewer = count(connection, f"""
        SELECT COUNT(*) FROM (
            SELECT o.badge_id FROM officers o
            JOIN fingerprint_scans s ON s.badge_id = o.badge_id
            WHERE o.first_name = '{FIRST_NAME}'
            GROUP BY o.badge_id HAVING COUNT(*) < {culprit_scans})
    """)
    more = count(connection, f"""
        SELECT COUNT(*) FROM (
            SELECT o.badge_id FROM officers o
            JOIN fingerprint_scans s ON s.badge_id = o.badge_id
            WHERE o.first_name = '{FIRST_NAME}'
            GROUP BY o.badge_id HAVING COUNT(*) > {culprit_scans})
    """)
    require(fewer == README_FEWER_SCANS and more == README_MORE_SCANS,
            f"{fewer} Bobs scanned less often than the culprit and {more} more"
            f" often, not {README_FEWER_SCANS} and {README_MORE_SCANS}")

    # The strange surname is not the odd one out.
    require(
        count(connection, f"""
            SELECT COUNT(*) FROM officers
            WHERE last_name IN {UNUSUAL_SURNAMES} AND first_name = '{FIRST_NAME}'
        """) == len(UNUSUAL_SURNAMES),
        "the unusual surnames are not all on Bobs",
    )
    odd = names_having(connection, f"o.last_name IN {UNUSUAL_SURNAMES}",
                       f"MAX(s.date) < {this_month}")
    require(odd == [],
            f"an officer with an unusual surname is also missing this month: {odd}")

    # The log itself: a clock-in a day, real dates, real times, nothing orphaned.
    scans = count(connection, "SELECT COUNT(*) FROM fingerprint_scans")
    require(scans == README_SCAN_ROWS,
            f"the log holds {scans} scans, not {README_SCAN_ROWS}")
    require(
        count(connection, "SELECT COUNT(DISTINCT badge_id) FROM fingerprint_scans"
              ) == OFFICER_COUNT,
        "an officer has no scan at all, which the LEFT JOIN and NOT IN forms"
        " of the solution would accuse along with the culprit",
    )
    require(
        count(connection, """
            SELECT COUNT(*) FROM (
                SELECT badge_id, date FROM fingerprint_scans
                GROUP BY badge_id, date HAVING COUNT(*) > 1)
        """) == 0,
        "somebody clocked in twice in one day",
    )
    require(
        count(connection, """
            SELECT COUNT(*) FROM fingerprint_scans
            WHERE time % 100 >= 60 OR time < 0 OR time > 2359
        """) == 0,
        "a logged time is not a real clock time",
    )
    require(
        count(connection, f"""
            SELECT COUNT(*) FROM fingerprint_scans
            WHERE date < {stamp(LOG_START)} OR date > {stamp(TODAY)}
        """) == 0,
        "a scan is dated outside the window the log covers",
    )
    stamped = {stamp(day) for day in DAYS}
    logged = {row[0] for row in
              connection.execute("SELECT DISTINCT date FROM fingerprint_scans")}
    require(logged <= stamped,
            "a logged date is not a real date in the log's window")
    require(
        count(connection, "SELECT MAX(date) FROM fingerprint_scans") == stamp(TODAY),
        "the log does not reach today, which the memo prints",
    )
    require(
        count(connection, "SELECT MIN(date) FROM fingerprint_scans"
              ) == stamp(LOG_START),
        "the log does not start where the memo says it does",
    )
    require(
        count(connection, """
            SELECT COUNT(*) FROM fingerprint_scans s
            LEFT JOIN officers o ON o.badge_id = s.badge_id
            WHERE o.badge_id IS NULL
        """) == 0,
        "a scan belongs to no officer on the roster",
    )
    require(
        count(connection, f"SELECT COUNT(*) FROM fingerprint_scans "
                          f"WHERE door NOT IN {DOORS}") == 0,
        "a scan came from a door that is not in the building",
    )

    # Numbering, and where the culprit sits in it.
    for table, column, digits, rows in (
        ("officers", "badge_id", BADGE_DIGITS, OFFICER_COUNT),
        ("fingerprint_scans", "scan_id", SCAN_DIGITS, scans),
    ):
        require(
            count(connection, f"""
                SELECT COUNT(*) FROM {table}
                WHERE {column} < {10 ** (digits - 1)} OR {column} > {10 ** digits - 1}
            """) == 0,
            f"a {table}.{column} is not {digits} digits long",
        )
        require(
            count(connection, f"SELECT COUNT(DISTINCT {column}) FROM {table}") == rows,
            f"{table}.{column} is not unique",
        )
    require(
        count(connection, "SELECT COUNT(DISTINCT first_name || ' ' || last_name)"
                          " FROM officers") == OFFICER_COUNT,
        "two officers share a full name",
    )
    place = count(connection, f"""
        SELECT COUNT(*) FROM officers
        WHERE badge_id <= (SELECT badge_id FROM officers
                           WHERE first_name || ' ' || last_name = '{CULPRIT_NAME}')
    """)
    require(OFFICER_COUNT // 10 < place < OFFICER_COUNT - OFFICER_COUNT // 10,
            "the culprit sits at one end of the roster")

    print(f"Wrote {DATABASE_PATH}")
    print(f"Culprit: {CULPRIT_NAME}, last seen {stamp(LAST_MONTH_END)},"
          f" no scan at all on or after {this_month}")
    print(f"{OFFICER_COUNT} officers ({BOB_COUNT} called {FIRST_NAME},"
          f" {NEAR_MISS_COUNT} called {NEAR_MISS_NAME}), {scans} scans logged"
          f" from {stamp(LOG_START)} to {stamp(TODAY)}")
    print("Asking about this month's scans accuses nobody, and being strict"
          f" about the 30th accuses nobody named {FIRST_NAME}")
    print(f"Dropping the name filter accuses {len(everyone)};"
          f" LIKE '{FIRST_NAME}%' accuses {len(prefix)};"
          f" last seen on 1 October are {len(edge)} innocent men")
    print(f"The culprit has {culprit_scans} scans: {fewer} Bobs have fewer and"
          f" {more} have more, and the fewest in the log is {fewest[0]}")

def count(connection: sqlite3.Connection, query: str):
    row = connection.execute(query).fetchone()
    return row[0] if row else None

def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)

def main() -> None:
    # CREATE TABLE IF NOT EXISTS plus INSERT would append to an existing file,
    # so start from scratch on every run.
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATABASE_PATH.unlink(missing_ok=True)
    random.seed(SEED)
    create_tables()

if __name__ == "__main__":
    main()
