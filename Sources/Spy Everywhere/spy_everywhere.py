"""
Generates the SQLite database for the custom case "Spy Everywhere".

Lindenhall Community Hall runs ten activity groups, two on each weekday
evening, so no member can physically attend more than five of them. Everybody
signs up for the two or three they actually go to -- except one member, a spy,
who filed a sign-up sheet for all ten so as to have a reason to be in the
building on any evening. They are not there for the pottery.

Dates are whole numbers, written the way the desk stamps them: 20260304 is the
4th of March 2026. As in the other four cases, nothing in the database is
fractional, and the sign-up desk only opens on weekdays, so no stamped date
lands on a weekend.

The difficulty lives in the data distribution rather than in any rule engine,
and here it is a single trap that punishes counting sheets instead of counting
groups -- a member who renews a group in the second half of the term files a
second sheet for it:

  * the culprit filed eleven sheets across ten groups, so `COUNT(*) = 10`
    accuses four members and never the culprit;
  * those four filed ten sheets across nine groups, which is what makes that
    wrong query look like it worked;
  * `COUNT(*) >= 10` accuses five, the culprit among them, so the player still
    cannot tell which;
  * six more members reached nine groups with nine sheets, so counting groups
    but settling for `>= 9` accuses eleven;
  * twelve members never signed up for anything, so a `LEFT JOIN` has to cope
    with NULL.

Ordinary members are capped below nine groups and below nine sheets by
`build_signups()`, which is what makes all of those counts exact by
construction rather than by luck, the same way `compliant_speed()` pins them in
`school_speed_limit.py`.

The culprit's eleven dates are spread across the whole term and are never the
earliest or the latest sheet on file, so sorting by date gives the answer away
to nobody -- the only way through is to count distinct groups.

`verify()` asserts all of the above and runs automatically, so the script
refuses to leave an unsolvable database behind.

Run from anywhere:  python3 "Sources/Spy Everywhere/spy_everywhere.py"
"""
import random
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import List, Tuple

# db_utils and its name lists come from the upstream workshop kit, which is
# vendored as a submodule and deliberately left untouched -- so reach into it
# rather than copying it out.
REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "dbd-workshop" / "Scripts"))

from db_utils import create_populate_table, database_connection, get_random_name

DATABASE_NAME = "clubhouse"
DATABASE_PATH = REPO / "Spy Everywhere" / DATABASE_NAME # straight into the case folder

SEED = 20260112 # fixed, so a rebuild reproduces the shipped case exactly --
                # the evidence artwork and README quote figures from this data
CULPRIT_NAME = "James Bond" # pinned by name, the way the other cases pin theirs

MEMBER_COUNT = 70

# Ten groups, two on each weekday evening. The clash is the whole premise: five
# evenings cannot hold ten attendances, so a sheet for all ten is a lie.
# `groups` is a SQLite keyword, which is why the table is called `activities`.
ACTIVITIES = (
    ("Chess Club", "Monday"),
    ("Choir", "Monday"),
    ("Debate Society", "Tuesday"),
    ("Film Club", "Tuesday"),
    ("Gardening Circle", "Wednesday"),
    ("Hiking Group", "Wednesday"),
    ("Pottery Studio", "Thursday"),
    ("Robotics Team", "Thursday"),
    ("Swim Squad", "Friday"),
    ("Theatre Troupe", "Friday"),
)
ACTIVITY_COUNT = len(ACTIVITIES)
ACTIVITY_IDS = tuple(range(1, ACTIVITY_COUNT + 1))

# The term the desk was open. Dates are stamped YYYYMMDD, and the desk only
# opens on weekdays.
TERM_FIRST = date(2026, 1, 12)
TERM_LAST = date(2026, 12, 4)

CULPRIT_SHEETS = ACTIVITY_COUNT + 1 # the eleventh is a renewal, which is the trap
CULPRIT_MIN_SPAN_DAYS = 240 # the culprit's sheets must cover most of the term,
                            # or sorting by date would name them for free

NEAR_MISS_GROUPS = ACTIVITY_COUNT - 1 # nine: as close as anyone honest gets
DUPLICATE_TEN_COUNT = 4 # nine groups, ten sheets -- what `COUNT(*) = 10` finds
NINE_GROUP_COUNT = 6    # nine groups, nine sheets
NO_SIGNUP_COUNT = 12    # no rows in signups at all

# Everyone else. Capped well below nine of each, which is what fixes every
# suspect count below by construction instead of by the draw.
ORDINARY_GROUPS = (1, 7)
ORDINARY_RENEWALS = (0, 1)

# Figures quoted on the evidence artwork, which verify() checks against the
# database so a rebuild that changes the data fails instead of quietly making
# the artwork lie.
ARTWORK_GROUPS = ACTIVITY_COUNT # the board lists them; the notice is stamped "all ten"
README_NINE_GROUP_MEMBERS = DUPLICATE_TEN_COUNT + NINE_GROUP_COUNT # ten
# Not fixed by construction the way the counts are -- it falls out of the seeded
# draw, which is exactly why verify() pins it.
README_SHEETS_FILED = 329

# Figures quoted in the case README, each one a wrong query's answer, all fixed
# by construction. verify() proves every one of them.
README_SHEETS_TEN_SUSPECTS = DUPLICATE_TEN_COUNT                  # COUNT(*) = 10
README_SHEETS_TEN_OR_MORE = DUPLICATE_TEN_COUNT + 1               # COUNT(*) >= 10
README_NINE_OR_MORE_SUSPECTS = README_NINE_GROUP_MEMBERS + 1     # COUNT(DISTINCT) >= 9
README_NO_SIGNUP_MEMBERS = NO_SIGNUP_COUNT

@database_connection(str(DATABASE_PATH))
def create_tables(connection: sqlite3.Connection) -> None:
    member_rows = build_members()
    activity_rows = build_activities()
    signup_rows = build_signups(member_rows)
    create_members_table(connection, member_rows)
    create_activities_table(connection, activity_rows)
    create_signups_table(connection, signup_rows)
    verify(connection)

def build_members() -> List[dict]:
    """
    Every member of the hall. The culprit sits somewhere in the middle of the
    list rather than at either end.
    """
    culprit_id = random.randint(2, MEMBER_COUNT - 1) # never first, never last
    taken_names = {CULPRIT_NAME}
    return [
        {
            "member_id": member_id,
            "name": CULPRIT_NAME if member_id == culprit_id else next_name(taken_names),
        }
        for member_id in range(1, MEMBER_COUNT + 1)
    ]

def build_activities() -> List[dict]:
    "The ten groups on the noticeboard, two to each weekday evening."
    return [
        {"activity_id": activity_id, "name": name, "meeting_day": day}
        for activity_id, (name, day) in zip(ACTIVITY_IDS, ACTIVITIES)
    ]

def build_signups(member_rows: List[dict]) -> List[dict]:
    """
    Every sheet filed at the desk this term. One member signed up for all ten
    groups; a handful of others got close enough to punish a sloppy count; the
    rest signed up for the two or three they actually attend.
    """
    culprit_id = next(
        row["member_id"] for row in member_rows if row["name"] == CULPRIT_NAME
    )
    others = [row["member_id"] for row in member_rows if row["member_id"] != culprit_id]
    marked = random.sample(
        others, NO_SIGNUP_COUNT + DUPLICATE_TEN_COUNT + NINE_GROUP_COUNT
    )
    no_signup = set(marked[:NO_SIGNUP_COUNT])
    duplicate_ten = marked[NO_SIGNUP_COUNT:NO_SIGNUP_COUNT + DUPLICATE_TEN_COUNT]
    nine_group = marked[NO_SIGNUP_COUNT + DUPLICATE_TEN_COUNT:]

    sheets: List[Tuple[int, int]] = []
    enrol(sheets, culprit_id, ACTIVITY_COUNT, CULPRIT_SHEETS - ACTIVITY_COUNT)
    for member_id in duplicate_ten:
        enrol(sheets, member_id, NEAR_MISS_GROUPS, 1)
    for member_id in nine_group:
        enrol(sheets, member_id, NEAR_MISS_GROUPS, 0)
    for member_id in others:
        if member_id in no_signup or member_id in duplicate_ten or member_id in nine_group:
            continue
        enrol(
            sheets,
            member_id,
            random.randint(*ORDINARY_GROUPS),
            random.randint(*ORDINARY_RENEWALS),
        )

    signup_rows = [
        {"member_id": member_id, "activity_id": activity_id, "signup_date": random_date()}
        for member_id, activity_id in sheets
    ]
    spread_culprit_dates(signup_rows, culprit_id)

    # Sorted by the date on the sheet, so the culprit's are not conspicuously
    # first in the table.
    signup_rows.sort(
        key=lambda row: (row["signup_date"], row["member_id"], row["activity_id"])
    )
    for signup_id, row in enumerate(signup_rows, start=1):
        row["signup_id"] = signup_id
    return signup_rows

def enrol(sheets: List[tuple], member_id: int, groups: int, renewals: int) -> None:
    """
    Files this member's sheets: one per group they joined, plus a second sheet
    for `renewals` of those groups. The renewal is what makes counting sheets
    give a different answer from counting groups.
    """
    joined = random.sample(ACTIVITY_IDS, groups)
    for activity_id in joined + random.sample(joined, renewals):
        sheets.append((member_id, activity_id))

def random_date() -> int:
    """
    A date the desk could have stamped: a weekday inside the term, written
    YYYYMMDD the way it appears on the sheet.
    """
    span = (TERM_LAST - TERM_FIRST).days
    while True:
        day = TERM_FIRST + timedelta(days=random.randint(0, span))
        if day.weekday() < 5: # the desk does not open at the weekend
            return day.year * 10000 + day.month * 100 + day.day

def spread_culprit_dates(signup_rows: List[dict], culprit_id: int) -> None:
    """
    Redraws the culprit's dates until they cover most of the term and are
    neither the earliest nor the latest sheet on file. Without this the draw
    could cluster all eleven into a fortnight, and `ORDER BY signup_date` would
    hand over the answer without counting anything.
    """
    culprit_rows = [row for row in signup_rows if row["member_id"] == culprit_id]
    others = [row["signup_date"] for row in signup_rows if row["member_id"] != culprit_id]
    first, last = min(others), max(others)
    while True:
        dates = [row["signup_date"] for row in culprit_rows]
        span = (as_date(max(dates)) - as_date(min(dates))).days
        if span >= CULPRIT_MIN_SPAN_DAYS and min(dates) > first and max(dates) < last:
            return
        for row in culprit_rows:
            row["signup_date"] = random_date()

def as_date(stamped: int) -> date:
    "Turns a stamped YYYYMMDD back into a date, which also proves it is one."
    return date(stamped // 10000, stamped // 100 % 100, stamped % 100)

def next_name(taken: set) -> str:
    "A unique member name, so the arrest is never ambiguous."
    while True:
        first_name, last_name = get_random_name()
        name = f"{first_name} {last_name}"
        if name not in taken:
            taken.add(name)
            return name

def create_members_table(connection: sqlite3.Connection, member_rows: List[dict]) -> None:
    create_populate_table(connection, "members", {
        "member_id": "INTEGER",
        "name": "TEXT",
    }, member_rows)

def create_activities_table(connection: sqlite3.Connection, activity_rows: List[dict]) -> None:
    create_populate_table(connection, "activities", {
        "activity_id": "INTEGER",
        "name": "TEXT",
        "meeting_day": "TEXT",
    }, activity_rows)

def create_signups_table(connection: sqlite3.Connection, signup_rows: List[dict]) -> None:
    create_populate_table(connection, "signups", {
        "signup_id": "INTEGER",
        "member_id": "INTEGER",
        "activity_id": "INTEGER",
        "signup_date": "INTEGER",
    }, signup_rows)

MEMBERSHIPS = """
    SELECT m.member_id     AS member_id,
           m.name          AS name,
           s.activity_id   AS activity_id,
           s.signup_date   AS signup_date
    FROM members m
    JOIN signups s ON s.member_id = m.member_id
"""

GROUPS_JOINED = "COUNT(DISTINCT activity_id)"
SHEETS_FILED = "COUNT(*)"

def names_having(connection: sqlite3.Connection, having: str) -> List[str]:
    "Runs a solution attempt and returns the members it accuses."
    query = f"""
        SELECT name FROM ({MEMBERSHIPS})
        GROUP BY member_id, name
        HAVING {having}
        ORDER BY name
    """
    return [row[0] for row in connection.execute(query)]

def verify(connection: sqlite3.Connection) -> None:
    "Fails loudly rather than leaving an unsolvable case behind."
    solution = f"{GROUPS_JOINED} = {ACTIVITY_COUNT}"
    accused = names_having(connection, solution)
    require(
        accused == [CULPRIT_NAME],
        f"the intended solution should name only {CULPRIT_NAME}, got {accused}",
    )

    sheets_ten = names_having(connection, f"{SHEETS_FILED} = {ACTIVITY_COUNT}")
    require(
        len(sheets_ten) == README_SHEETS_TEN_SUSPECTS and CULPRIT_NAME not in sheets_ten,
        f"`COUNT(*) = {ACTIVITY_COUNT}` should accuse {README_SHEETS_TEN_SUSPECTS}"
        f" members and never the culprit, got {sheets_ten}",
    )

    sheets_ten_or_more = names_having(connection, f"{SHEETS_FILED} >= {ACTIVITY_COUNT}")
    require(
        len(sheets_ten_or_more) == README_SHEETS_TEN_OR_MORE
        and CULPRIT_NAME in sheets_ten_or_more,
        f"`COUNT(*) >= {ACTIVITY_COUNT}` should accuse {README_SHEETS_TEN_OR_MORE}"
        f" members including the culprit, got {sheets_ten_or_more}",
    )

    nine_or_more = names_having(connection, f"{GROUPS_JOINED} >= {NEAR_MISS_GROUPS}")
    require(
        len(nine_or_more) == README_NINE_OR_MORE_SUSPECTS and CULPRIT_NAME in nine_or_more,
        f"`{GROUPS_JOINED} >= {NEAR_MISS_GROUPS}` should accuse"
        f" {README_NINE_OR_MORE_SUSPECTS} members, got {len(nine_or_more)}",
    )

    nine_exactly = names_having(connection, f"{GROUPS_JOINED} = {NEAR_MISS_GROUPS}")
    require(
        len(nine_exactly) == README_NINE_GROUP_MEMBERS and CULPRIT_NAME not in nine_exactly,
        f"the README quotes {README_NINE_GROUP_MEMBERS} members in"
        f" {NEAR_MISS_GROUPS} groups, found {len(nine_exactly)}",
    )
    require(
        count(connection, f"""
            SELECT COUNT(*) FROM (
                SELECT member_id FROM ({MEMBERSHIPS}) GROUP BY member_id
                HAVING {GROUPS_JOINED} > {NEAR_MISS_GROUPS}
            )
        """) == 1,
        f"somebody other than the culprit reached all {ACTIVITY_COUNT} groups",
    )

    culprit_sheets = count(connection, f"""
        SELECT COUNT(*) FROM ({MEMBERSHIPS}) WHERE name = '{CULPRIT_NAME}'
    """)
    culprit_groups = count(connection, f"""
        SELECT COUNT(DISTINCT activity_id) FROM ({MEMBERSHIPS})
        WHERE name = '{CULPRIT_NAME}'
    """)
    require(
        culprit_sheets == CULPRIT_SHEETS and culprit_groups == ACTIVITY_COUNT,
        f"the culprit should file {CULPRIT_SHEETS} sheets across {ACTIVITY_COUNT}"
        f" groups, found {culprit_sheets} across {culprit_groups}",
    )

    culprit_dates = [row[0] for row in connection.execute(f"""
        SELECT signup_date FROM ({MEMBERSHIPS}) WHERE name = '{CULPRIT_NAME}'
        ORDER BY signup_date
    """)]
    span = (as_date(culprit_dates[-1]) - as_date(culprit_dates[0])).days
    require(
        span >= CULPRIT_MIN_SPAN_DAYS,
        f"the culprit's sheets span {span} days, which is narrow enough for"
        " ORDER BY signup_date to give the answer away",
    )
    first, last = connection.execute(
        "SELECT MIN(signup_date), MAX(signup_date) FROM signups"
    ).fetchone()
    require(
        culprit_dates[0] > first and culprit_dates[-1] < last,
        "the culprit holds the earliest or the latest sheet on file, which"
        " points at them without counting anything",
    )

    no_signups = count(connection, """
        SELECT COUNT(*) FROM members m
        LEFT JOIN signups s ON s.member_id = m.member_id
        WHERE s.signup_id IS NULL
    """)
    require(
        no_signups == README_NO_SIGNUP_MEMBERS,
        f"the README quotes {README_NO_SIGNUP_MEMBERS} members who never signed"
        f" up, found {no_signups}",
    )

    groups = count(connection, "SELECT COUNT(*) FROM activities")
    require(
        groups == ARTWORK_GROUPS,
        f"the artwork quotes {ARTWORK_GROUPS} groups, found {groups}",
    )
    require(
        count(connection, "SELECT COUNT(DISTINCT meeting_day) FROM activities") == 5
        and count(connection, """
            SELECT MIN(members) FROM (
                SELECT COUNT(*) AS members FROM activities GROUP BY meeting_day
            )
        """) == 2,
        "the groups should sit two to each of five weekday evenings, so that"
        f" attending all {ACTIVITY_COUNT} is impossible",
    )
    thinnest = count(connection, f"""
        SELECT MIN(members) FROM (
            SELECT COUNT(DISTINCT member_id) AS members FROM ({MEMBERSHIPS})
            GROUP BY activity_id
        )
    """)
    require(
        thinnest >= 15,
        f"one group has only {thinnest} members, which makes its roster short"
        " enough to read the answer off directly",
    )
    require(
        count(connection, f"""
            SELECT COUNT(*) FROM (
                SELECT activity_id FROM ({MEMBERSHIPS}) GROUP BY activity_id
            )
        """) == ACTIVITY_COUNT,
        "a group has nobody signed up for it at all",
    )

    filed = count(connection, "SELECT COUNT(*) FROM signups")
    require(
        filed == README_SHEETS_FILED,
        f"the README quotes {README_SHEETS_FILED} sheets filed, found {filed}",
    )

    require(
        count(connection, """
            SELECT COUNT(*) FROM signups s
            LEFT JOIN members m ON m.member_id = s.member_id
            WHERE m.name IS NULL
        """) == 0,
        "a sheet was filed by nobody",
    )
    require(
        count(connection, """
            SELECT COUNT(*) FROM signups s
            LEFT JOIN activities a ON a.activity_id = s.activity_id
            WHERE a.name IS NULL
        """) == 0,
        "a sheet was filed for a group that does not exist",
    )
    require(
        count(connection, "SELECT COUNT(DISTINCT name) FROM members") == MEMBER_COUNT,
        "member names are not unique",
    )
    require(
        count(connection, """
            SELECT COUNT(*) FROM signups
            WHERE signup_date <> CAST(signup_date AS INTEGER)
        """) == 0,
        "a stamped date is not a whole number",
    )
    for stamped, in connection.execute("SELECT DISTINCT signup_date FROM signups"):
        stamp = as_date(stamped) # raises if it is not a real calendar date
        require(
            TERM_FIRST <= stamp <= TERM_LAST and stamp.weekday() < 5,
            f"{stamped} is outside the term or falls at the weekend, when the"
            " desk is shut",
        )

    print(f"Wrote {DATABASE_PATH}")
    print(f"Culprit: {CULPRIT_NAME}, {culprit_sheets} sheets across all"
          f" {culprit_groups} groups, spanning {span} days")
    print(f"{MEMBER_COUNT} members, {groups} groups, {filed} sheets filed,"
          f" {no_signups} members who never signed up")
    print(f"`COUNT(*) = {ACTIVITY_COUNT}` accuses {len(sheets_ten)} members and not"
          " the culprit; `>=` accuses"
          f" {len(sheets_ten_or_more)}")
    print(f"`{GROUPS_JOINED} >= {NEAR_MISS_GROUPS}` accuses {len(nine_or_more)};"
          f" {len(nine_exactly)} members stopped at {NEAR_MISS_GROUPS} groups")
    print(f"The thinnest group roster is {thinnest} members")

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
