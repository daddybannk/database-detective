"""
Generates the SQLite database for the custom case "Vibe Code 👉👈".

On Friday 9 October 2026 somebody in IT ran a migration an AI had written for
them against the production database. Every table went but one. The survivor
is `employees`, and it survived precisely because it is the thing the migration
was written to replace: a legacy key/value store that keeps one row per
property per person rather than one row per person. The script dropped the
normal tables first and never reached it.

So the case ships a single table, in the shape the store keeps it:

    employees(emp_code TEXT, emp_property TEXT, value TEXT)

    DOMN5523|first_name|Dovid
    DOMN5523|last_name|Brooks
    DOMN5523|department|IT
    DOMN5523|role|Manager
    DOMN5523|date_of_birth|19960222
    DOMN5523|start_date|20261009

Every column is TEXT. `value` has to be, because it holds names as well as
dates, so the dates are TEXT with it -- '20261008' rather than 20261008 --
and the staff code is four letters and four digits rather than a number.
Fixed-width YYYYMMDD still compares and sorts correctly as text, and the Int32
ceiling the game reads an INTEGER column into cannot be reached, because there
is no INTEGER column to reach it with.

The evidence gives three facts: the department, the role, and the day he
started -- the chat log is stamped the Friday and he calls it his second day.
The wall a player hits first is that the obvious query cannot work, because
one row holds one property:

    WHERE emp_property = 'department' AND value = 'IT'
      AND emp_property = 'role'       AND value = 'Junior'   -- no rows, ever

The way through is to pivot the store back into a row with a self join on
`emp_code`, five aliases: two to read the name back and three to carry a clue
each.

    SELECT e.emp_code, e.value, l.value, r.value, s.value
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

Every clue is load bearing, and **the date is the one that took work**. A date
is a narrow filter, so the day he started has to be crowded or it answers on
its own and leaves the other two decorative. Thirty five people came in that
Thursday, six of them in IT and ten of them juniors, and no second IT junior:

  * drop the role and seven answer;
  * drop the department and eleven answer;
  * the date on its own answers with thirty five;
  * drop the date and eleven answer -- every IT junior on the books. That is
    the one clue whose loss still leaves a road to him, because sorting those
    eleven by start_date puts him first, and the incident report calls him the
    newest junior IT has taken on. Both roads are intended and verify() checks
    both.

**The in-game console has no LIMIT**, which is why the intended solution is
one row rather than the top of a list, and why the sort route needs its own
decoys: a player reads the first row whatever they typed, so the row a wrong
sort puts first has to be somebody innocent. Eight people started the Friday
after him, not one of them an IT junior, so sorting IT without the role filter
tops out at the manager, sorting juniors without the department filter tops
out in another department, and sorting the whole payroll tops out on the
Friday. A second IT junior started six days before him, so reading the sort is
a judgement rather than a matter of spotting the only date in October.

Ties are the thing to watch wherever a sort decides anything: SQL does not say
which of a tied group comes first, so verify() counts the rows *strictly*
newer than the culprit rather than reading his row position. Strictly newer is
the only kind of row guaranteed to sit above him in every engine.

Two more orderings are closed off deliberately. A staff code is drawn, not
counted, so sorting by it says nothing about seniority -- but where the
culprit's lands is luck, so centre_culprit_code() swaps it with whoever holds
the middle one if the draw puts him at either end, and verify() checks both
that and how far October's starters are spread across the ordering. And the
culprit is not the youngest employee, so sorting `date_of_birth` does not find
him either.

`verify()` asserts all of the above and runs automatically, so the script
refuses to leave an unsolvable database behind.

Run from anywhere:  python3 "Sources/Vibe Code/vibe_code.py"
"""
import random
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path
from string import ascii_uppercase
from typing import List, Sequence, Tuple

# db_utils and its name lists come from the upstream workshop kit, which is
# vendored as a submodule and deliberately left untouched -- so reach into it
# rather than copying it out.
REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "dbd-workshop" / "Scripts"))

from db_utils import create_populate_table, database_connection, get_random_name

DATABASE_NAME = "hr_system"
DATABASE_PATH = REPO / "Vibe Code" / DATABASE_NAME # straight into the case folder

SEED = 20261009 # fixed, so a rebuild reproduces the shipped case exactly --
                # the evidence artwork and README quote figures from this data

CULPRIT_NAME = "Cole Finley" # pinned by name, the way the other cases pin theirs
INTERN_NAME = "Trevor Gaines" # the intern who started the same morning: the
                              # trap for a player who reads "the new kid" as
                              # "the youngest job title on the floor"
MANAGER_NAME = "Dovid Brooks" # emp_code 101, the row quoted in the docstring

EMPLOYEE_COUNT = 301
# Every employee is keyed by a code rather than a number: four letters and
# four digits, drawn at random. It is TEXT like everything else here, so the
# table has no INTEGER column at all and the Int32 ceiling the game reads one
# into cannot be reached. It also carries no ordering a player could mistake
# for seniority, which a run of numbers would.
EMP_CODE_LETTERS = 4
EMP_CODE_DIGITS = 4

# The six properties the store keeps, in the order a dump prints them. Every
# employee has all six: no record is incomplete, so a player who pivots the
# whole table sees everybody.
PROPERTIES = (
    "first_name",
    "last_name",
    "department",
    "role",
    "date_of_birth",
    "start_date",
)

DEPARTMENTS = ("IT", "Sales", "Finance", "HR", "Logistics", "Support")
ROLES = ("Manager", "Senior", "Junior", "Intern")

INCIDENT = date(2026, 10, 9) # the Friday the migration ran
TODAY = date(2026, 10, 10)

# The three October days the case is built on. The culprit came in on the
# Thursday, the day before the migration ran.
CULPRIT_START = "20261008"
NEWER_START = "20261009"
NEAR_MISS_START = "20261002" # the IT junior who started six days before him, so
                             # that reading the sort is a judgement and not a
                             # matter of spotting the only October date
PINNED_START_DATES = (NEAR_MISS_START, CULPRIT_START, NEWER_START)

# The three clues the evidence gives, as (property, value) pairs. The chat log
# is stamped the Friday and the new starter says it is his second day, which is
# where the date comes from. The data is built from this tuple and verify()
# tests the player's query against the same tuple, so the checks cannot drift
# from the puzzle.
CLUES = (
    ("department", "IT"),
    ("role", "Junior"),
    ("start_date", CULPRIT_START),
)
CLUE_DEPARTMENT = CLUES[0][1]
CLUE_ROLE = CLUES[1][1]
SORT_CLUES = CLUES[:2] # the second road in: drop the date, sort the eleven IT
                       # juniors by start_date and read the top row

# His own Thursday is the case's decoy table, and it is big. Thirty four people
# came in with him, six of them in IT and ten of them juniors, but no second IT
# junior -- so the date pins him only once both other clues are on the query.
# Without that mix the date would make the other two redundant: forget either
# and the answer would still come back alone, which is the one thing a wrong
# query must never do.
CULPRIT_DAY_IT_NOT_JUNIOR = 6
CULPRIT_DAY_JUNIOR_NOT_IT = 10
CULPRIT_DAY_NEITHER = 18
CULPRIT_DAY_TOTAL = (
    1 + CULPRIT_DAY_IT_NOT_JUNIOR + CULPRIT_DAY_JUNIOR_NOT_IT + CULPRIT_DAY_NEITHER
) # thirty five

# The Friday after him. Eight people, not one of them an IT junior, which is
# what keeps every `newest` query -- newest in IT, newest junior, newest on the
# payroll -- off him when the date is left off and the sort does the work.
NEWER_IT_NOT_JUNIOR = 2 # the manager and the intern
NEWER_JUNIOR_NOT_IT = 4
NEWER_NEITHER = 2
NEWER_TOTAL = NEWER_IT_NOT_JUNIOR + NEWER_JUNIOR_NOT_IT + NEWER_NEITHER # eight

# Totals, fixed by construction rather than by the draw, so verify() can assert
# the exact number a wrong query accuses instead of just "more than one".
IT_TOTAL = 44
JUNIOR_TOTAL = 82
IT_JUNIOR_TOTAL = 11 # the culprit, the near miss, and nine already on the floor

EARLIER_IT_JUNIORS = IT_JUNIOR_TOTAL - 2 # the culprit and the near miss are the
                                         # other two
# Whatever is left of each total once the pinned October groups have taken
# their share, so IT_TOTAL and JUNIOR_TOTAL come out exact however the October
# groups are resized.
ORDINARY_IT = (
    IT_TOTAL - 1 - CULPRIT_DAY_IT_NOT_JUNIOR - NEWER_IT_NOT_JUNIOR
    - 1 - EARLIER_IT_JUNIORS
)
ORDINARY_JUNIORS = (
    JUNIOR_TOTAL - 1 - CULPRIT_DAY_JUNIOR_NOT_IT - NEWER_JUNIOR_NOT_IT
    - 1 - EARLIER_IT_JUNIORS
)
# If either of those goes negative the October groups have outgrown their
# total; verify() catches it, because it counts IT and Junior in the finished
# table against IT_TOTAL and JUNIOR_TOTAL.

# Hiring history. Everything outside those three October days stops in
# September, so the only start dates in October are the ones placed on purpose.
FOUNDED = date(2001, 1, 15)
LAST_ORDINARY_START = date(2026, 9, 30)

# The summer graduate hires. They exist for one reason: four of them are born
# after the culprit, so he is not the youngest person in the building. Drawing
# the ages from the start dates otherwise makes the newest hire the youngest by
# construction, and `ORDER BY value DESC` over date_of_birth would name him
# without a join -- the `Spy Everywhere` lesson about a second ordering.
GRADUATE_FIRST_START = date(2026, 6, 1)
GRADUATES = 4

# Nobody is hired under 22 or over 45, and nobody still on the payroll is over
# 67, which is what keeps every date_of_birth plausible against its own
# start_date rather than merely well formed.
MIN_AGE_AT_HIRE = 22
MAX_AGE_AT_HIRE = 45
MAX_AGE_NOW = 67

CULPRIT_BIRTH = "20040517" # twenty two the morning he started
MANAGER_BIRTH = "19960222" # the row quoted in the docstring, kept verbatim

# One deliberate collision across properties: somebody's start_date is the same
# eight characters as the culprit's date_of_birth. `value` is one column for
# every property, so a bare `WHERE value = '<a date>'` means two different
# things at once. verify() pins it, because the draw would not reliably produce
# one: the two ranges only overlap for the four years between the company's
# fifth birthday and the youngest employee's.
COLLIDING_VALUE = CULPRIT_BIRTH
COLLISION_ROWS = 2 # the culprit's date_of_birth and one other person's start_date

# Figures quoted in the case README and on the evidence artwork, each one a
# wrong query's answer. verify() proves every one of them.
README_ROW_COUNT = EMPLOYEE_COUNT * len(PROPERTIES)   # 1806
README_ALL_CLUES = 1                                  # the intended solution
# What each clue is worth: drop it and this many people answer instead.
README_WITHOUT_ROLE = 1 + CULPRIT_DAY_IT_NOT_JUNIOR        # seven
README_WITHOUT_DEPARTMENT = 1 + CULPRIT_DAY_JUNIOR_NOT_IT  # eleven
README_WITHOUT_DATE = IT_JUNIOR_TOTAL                      # eleven, and sortable
README_ON_HIS_OWN_DAY = CULPRIT_DAY_TOTAL                  # thirty five
# How many rows a wrong `newest` query puts strictly above him. None of these
# is zero, which is what keeps the second road in honest.
README_ABOVE_HIM_IN_IT = NEWER_IT_NOT_JUNIOR          # two
README_ABOVE_HIM_AMONG_JUNIORS = NEWER_JUNIOR_NOT_IT  # four
README_ABOVE_HIM_ON_THE_PAYROLL = NEWER_TOTAL         # eight
README_IT_JUNIORS = IT_JUNIOR_TOTAL                   # the list the sort route sorts
README_OR_ROWS = IT_TOTAL + JUNIOR_TOTAL + CULPRIT_DAY_TOTAL
README_OR_PEOPLE = 133 # the 161 rows belong to this many employees, which is
                       # the figure that says the OR names nobody
README_YOUNGER_THAN_CULPRIT = GRADUATES # a rebuild that leaves the culprit the
                                        # youngest in the building would hand
                                        # the answer to `ORDER BY value DESC`
README_OCTOBER_CODE_SPAN = 250 # October's starters are scattered across the
                                # not clustered at either end of it

@database_connection(str(DATABASE_PATH))
def create_tables(connection: sqlite3.Connection) -> None:
    employee_records = build_employees()
    employee_rows = build_rows(employee_records)
    create_employees_table(connection, employee_rows)
    verify(connection)

def build_employees() -> List[dict]:
    """
    One complete record per employee -- six property values apiece -- which
    build_rows() then flattens into the key/value shape the table keeps. The
    departments, roles and start dates come from fixed group sizes rather than
    from the draw, so every suspect count below is exact by construction.
    """
    slots = build_slots()
    slots = order_slots(slots)

    taken_names = {CULPRIT_NAME, INTERN_NAME, MANAGER_NAME}
    taken_codes = set()
    records = []
    for slot in slots:
        pinned = slot.get("name")
        first_name, last_name = (
            pinned.split(" ", 1) if pinned else next_name(taken_names)
        )
        records.append({
            "emp_code": next_emp_code(taken_codes),
            "first_name": first_name,
            "last_name": last_name,
            "department": slot["department"],
            "role": slot["role"],
            "date_of_birth": slot.get("date_of_birth")
                             or stamped(birth_date_for(as_date(slot["start_date"]))),
            "start_date": slot["start_date"],
        })
    collide_one_start_date(records)
    centre_culprit_code(records)
    return records

def build_slots() -> List[dict]:
    """
    Every employee's department, role and start date, group by group. The
    culprit, the three October days around him and the IT juniors already on
    the floor are placed deliberately; everybody else fills the remaining
    groups in fixed numbers.
    """
    slots = [
        # The culprit: the last IT junior onto the books, in on the Thursday.
        {
            "name": CULPRIT_NAME,
            "department": CLUE_DEPARTMENT,
            "role": CLUE_ROLE,
            "start_date": CULPRIT_START,
            "date_of_birth": CULPRIT_BIRTH,
        },
        # The two in IT who started the day after him. They are what a query
        # that sorts IT by start date without filtering the role finds first,
        # and neither of them is the man.
        {
            "name": MANAGER_NAME,
            "department": CLUE_DEPARTMENT,
            "role": "Manager",
            "start_date": NEWER_START,
            "date_of_birth": MANAGER_BIRTH,
        },
        {
            "name": INTERN_NAME,
            "department": CLUE_DEPARTMENT,
            "role": "Intern",
            "start_date": NEWER_START,
        },
        # The IT junior six days ahead of him in the sort: second row of the
        # intended query, and the reason reading it is a judgement.
        {
            "department": CLUE_DEPARTMENT,
            "role": CLUE_ROLE,
            "start_date": NEAR_MISS_START,
        },
    ]
    require(
        len(slots) == 2 + NEWER_IT_NOT_JUNIOR,
        "the pinned IT slots do not match NEWER_IT_NOT_JUNIOR plus the near miss",
    )

    # Juniors who started the day after him, in other departments. A query that
    # sorts juniors by start date without filtering the department finds these
    # four above him.
    for _ in range(NEWER_JUNIOR_NOT_IT):
        slots.append({
            "department": other_department(),
            "role": CLUE_ROLE,
            "start_date": NEWER_START,
        })
    # And the rest of that Friday, so that sorting the whole payroll by start
    # date puts eight people above him rather than a handful.
    for _ in range(NEWER_NEITHER):
        slots.append({
            "department": other_department(),
            "role": other_role(),
            "start_date": NEWER_START,
        })
    # The thirty four who started the same Thursday he did. Six are in IT and
    # ten are juniors, but none is both, so the date needs the other two clues
    # beside it: on its own it answers with thirty five people, with the role
    # dropped it answers with seven and with the department dropped eleven.
    for _ in range(CULPRIT_DAY_IT_NOT_JUNIOR):
        slots.append({
            "department": CLUE_DEPARTMENT,
            "role": other_role(),
            "start_date": CULPRIT_START,
        })
    for _ in range(CULPRIT_DAY_JUNIOR_NOT_IT):
        slots.append({
            "department": other_department(),
            "role": CLUE_ROLE,
            "start_date": CULPRIT_START,
        })
    for _ in range(CULPRIT_DAY_NEITHER):
        slots.append({
            "department": other_department(),
            "role": other_role(),
            "start_date": CULPRIT_START,
        })

    # The IT juniors already on the floor. These and the two above are the
    # eleven rows the intended query sorts.
    for _ in range(EARLIER_IT_JUNIORS):
        slots.append({
            "department": CLUE_DEPARTMENT,
            "role": CLUE_ROLE,
            "start_date": ordinary_start_date(),
        })
    # Everybody else in IT, none of them junior, which is what fixes IT_TOTAL.
    for _ in range(ORDINARY_IT):
        slots.append({
            "department": CLUE_DEPARTMENT,
            "role": other_role(),
            "start_date": ordinary_start_date(),
        })
    # Every other junior in the building, none of them in IT, which fixes
    # JUNIOR_TOTAL.
    for _ in range(ORDINARY_JUNIORS):
        slots.append({
            "department": other_department(),
            "role": CLUE_ROLE,
            "start_date": ordinary_start_date(),
        })
    # The summer graduates, who are the only people in the building younger
    # than the culprit.
    for _ in range(GRADUATES):
        slots.append(graduate_slot())
    # And the rest of the payroll, touched by none of the three clues.
    while len(slots) < EMPLOYEE_COUNT:
        slots.append({
            "department": other_department(),
            "role": other_role(),
            "start_date": ordinary_start_date(),
        })
    return slots

def order_slots(slots: List[dict]) -> List[dict]:
    """
    Shuffles the roster before the codes are handed out, so that no group ends
    up holding a run of codes drawn one after another. The codes themselves are
    random and the finished table is sorted by them, so neither the order of
    the table nor the code on a row says anything about when somebody joined.
    """
    pinned = {slot["name"]: slot for slot in slots if slot.get("name")}
    rest = [slot for slot in slots if not slot.get("name")]
    random.shuffle(rest)
    ordered = rest + list(pinned.values())
    random.shuffle(ordered)
    require(len(ordered) == EMPLOYEE_COUNT, "the roster is not the right size")
    return ordered

def build_rows(employee_records: List[dict]) -> List[dict]:
    """
    Flattens each record into one row per property -- the shape the store keeps
    and the whole of the puzzle. Rows come out grouped by emp_code and in the
    property order a dump prints, so the table reads like the one the evidence
    quotes.
    """
    return [
        {
            "emp_code": record["emp_code"],
            "emp_property": emp_property,
            "value": record[emp_property],
        }
        for record in sorted(employee_records, key=lambda record: record["emp_code"])
        for emp_property in PROPERTIES
    ]

def centre_culprit_code(records: List[dict]) -> None:
    """
    Puts the culprit's staff code somewhere in the middle of the code ordering.

    Where a drawn code lands is luck, and a rebuild that dropped his at either
    end would make `ORDER BY emp_code` worth a look -- the `Spy Everywhere`
    lesson about a second ordering giving the answer away. Swapping his code
    with whoever holds the middle one costs nothing, because both were drawn.
    """
    culprit = next(
        record for record in records
        if f"{record['first_name']} {record['last_name']}" == CULPRIT_NAME
    )
    in_order = sorted(record["emp_code"] for record in records)
    margin = EMPLOYEE_COUNT // 5
    if margin <= in_order.index(culprit["emp_code"]) <= EMPLOYEE_COUNT - 1 - margin:
        return
    middle_code = in_order[EMPLOYEE_COUNT // 2]
    middle = next(r for r in records if r["emp_code"] == middle_code)
    culprit["emp_code"], middle["emp_code"] = middle_code, culprit["emp_code"]

def collide_one_start_date(records: List[dict]) -> None:
    """
    Moves one ordinary employee's start date onto the culprit's date of birth,
    so that one eight character value in the table is a birthday to one person
    and a first day to another. `value` is a single column for every property;
    this is what proves that filtering it without filtering `emp_property` is
    meaningless, and it is pinned here rather than left to the draw.
    """
    eligible = [
        record for record in records
        if record["start_date"] not in PINNED_START_DATES
        and record["department"] != CLUE_DEPARTMENT
        and record["role"] != CLUE_ROLE
        and record["date_of_birth"] <= CULPRIT_BIRTH # never one of the graduates,
    ]                                               # who are here to be younger
    chosen = random.choice(eligible)
    chosen["start_date"] = COLLIDING_VALUE
    # Their own birthday has to stay plausible against the new first day.
    chosen["date_of_birth"] = stamped(birth_date_for(as_date(COLLIDING_VALUE)))

def graduate_slot() -> dict:
    """
    One summer graduate: hired in the months before the October intake and born
    in the weeks after the culprit, at the youngest age the company hires at.
    Their birthday is pinned into the slot rather than drawn from the start
    date, because the whole point of them is to sit on the far side of the
    culprit's.
    """
    start = weekday_between(GRADUATE_FIRST_START, LAST_ORDINARY_START)
    earliest = as_date(CULPRIT_BIRTH) + timedelta(days=1)
    latest = start - timedelta(days=MIN_AGE_AT_HIRE * 365)
    born = earliest + timedelta(days=random.randint(0, (latest - earliest).days))
    return {
        "department": other_department(),
        "role": other_role(),
        "start_date": stamped(start),
        "date_of_birth": stamped(born),
    }

def other_department() -> str:
    "Any department except the one the evidence names."
    return random.choice([name for name in DEPARTMENTS if name != CLUE_DEPARTMENT])

def other_role() -> str:
    """
    Any role except the one the evidence names. Managers are thin on the ground
    and interns thinner, the way they are in a real payroll.
    """
    roles = [name for name in ROLES if name != CLUE_ROLE]
    weights = [1 if name == "Manager" else 2 if name == "Intern" else 6 for name in roles]
    return random.choices(roles, weights=weights, k=1)[0]

def ordinary_start_date() -> str:
    """
    A weekday between the company's first and the end of September, stamped
    YYYYMMDD the way the store keeps it. Nothing starts in October except the
    intake, so the intake is the newest thing in the table.
    """
    return stamped(weekday_between(FOUNDED, LAST_ORDINARY_START))

def weekday_between(first: date, last: date) -> date:
    "A working day in the range: nobody's first day is a Saturday."
    span = (last - first).days
    while True:
        day = first + timedelta(days=random.randint(0, span))
        if day.weekday() < 5:
            return day

def birth_date_for(start: date) -> date:
    """
    A birthday that makes sense of this first day: hired somewhere between 22
    and 45, and not yet 67. Drawing it from the start date rather than from a
    flat range is what keeps the youngest people in the building the newest
    hires, so the intake does not stand out as a cohort of forty year olds.
    """
    while True:
        age = random.randint(MIN_AGE_AT_HIRE, MAX_AGE_AT_HIRE)
        born = start - timedelta(days=age * 365 + random.randint(0, 364))
        if (TODAY - born).days // 365 <= MAX_AGE_NOW:
            return born

def stamped(day: date) -> str:
    "YYYYMMDD as eight characters, because `value` is TEXT for every property."
    return f"{day.year:04d}{day.month:02d}{day.day:02d}"

def as_date(value: str) -> date:
    "Turns a stamped YYYYMMDD back into a date, which also proves it is one."
    return date(int(value[:4]), int(value[4:6]), int(value[6:]))

def next_emp_code(taken: set) -> str:
    """
    A unique staff code: four letters and four digits, as the store writes it.
    Drawn rather than counted, so that sorting by it tells a player nothing.
    """
    while True:
        code = "".join(random.choices(ascii_uppercase, k=EMP_CODE_LETTERS))
        code += f"{random.randrange(10 ** EMP_CODE_DIGITS):0{EMP_CODE_DIGITS}d}"
        if code not in taken:
            taken.add(code)
            return code

def next_name(taken: set) -> Tuple[str, str]:
    "A unique full name, so the arrest is never ambiguous."
    while True:
        first_name, last_name = get_random_name()
        if f"{first_name} {last_name}" not in taken:
            taken.add(f"{first_name} {last_name}")
            return first_name, last_name

def create_employees_table(connection: sqlite3.Connection, rows: List[dict]) -> None:
    # `value` holds names as well as dates, so it has to be TEXT, and the dates
    # with it. That is the one place this case departs from the others here.
    create_populate_table(connection, "employees", {
        "emp_code": "TEXT",
        "emp_property": "TEXT",
        "value": "TEXT",
    }, rows)

def sorted_by_start(
    connection: sqlite3.Connection, clues: Sequence[Tuple[str, str]]
) -> List[Tuple[str, str]]:
    """
    Runs the query a player actually types: the store pivoted back into a row
    by joining `employees` to itself on emp_code, every property named in the
    WHERE, and the result put in start_date order with the newest first.

    There is no LIMIT, because the in-game console has none. The answer is
    whatever sits in the top row, which is why it is not enough for a wrong
    query to return several people -- the row it puts first has to be somebody
    other than the culprit.
    """
    aliases = [
        (f"c{index}", emp_property, value)
        for index, (emp_property, value) in enumerate(clues, start=1)
    ]
    joins = "".join(
        f"\n        JOIN employees {alias} ON {alias}.emp_code = e.emp_code"
        for alias, _, _ in aliases
    )
    conditions = "".join(
        f"\n          AND {alias}.emp_property = '{emp_property}'"
        f" AND {alias}.value = '{value}'"
        for alias, emp_property, value in aliases
    )
    query = f"""
        SELECT e.value || ' ' || l.value AS name, s.value AS start_date
        FROM employees e
        JOIN employees l ON l.emp_code = e.emp_code
        JOIN employees s ON s.emp_code = e.emp_code{joins}
        WHERE e.emp_property = 'first_name'
          AND l.emp_property = 'last_name'
          AND s.emp_property = 'start_date'{conditions}
        ORDER BY s.value DESC
    """
    return [(name, start_date) for name, start_date in connection.execute(query)]

def without(clue: str) -> Tuple[Tuple[str, str], ...]:
    "The clue list with one clue dropped, which is how each one is shown to matter."
    return tuple(pair for pair in CLUES if pair[0] != clue)

def strictly_newer(rows: Sequence[Tuple[str, str]], start: str) -> int:
    """
    How many rows of a sorted result started later than this date.

    Counted rather than read off the culprit's row position, because people who
    started on the same day tie, and SQL does not say which of a tied group
    comes first. Only a strictly newer row is guaranteed to sit above him in
    every engine, so only a strictly newer row can be relied on to keep a wrong
    query off him.
    """
    require(
        any(name == CULPRIT_NAME for name, _ in rows),
        "the culprit fell out of a result he should be in",
    )
    return sum(1 for _, found in rows if found > start)

def verify(connection: sqlite3.Connection) -> None:
    "Fails loudly rather than leaving an unsolvable case behind."
    # The intended solution: three clues, one row. No sorting needed, which is
    # just as well, because the in-game console has no LIMIT and a sort would
    # leave the answer as "whatever printed first".
    solution = sorted_by_start(connection, CLUES)
    require(
        solution == [(CULPRIT_NAME, CULPRIT_START)],
        f"the three clues should name only {CULPRIT_NAME} on {CULPRIT_START},"
        f" got {solution}",
    )

    # The wall. One row holds one property, so asking for two on the same row
    # is not a hard query, it is an impossible one.
    impossible = count(connection, f"""
        SELECT COUNT(*) FROM employees
        WHERE emp_property = 'department' AND value = '{CLUE_DEPARTMENT}'
          AND emp_property = 'role'       AND value = '{CLUE_ROLE}'
    """)
    require(
        impossible == 0,
        "the single row AND should be impossible by construction, got"
        f" {impossible} rows",
    )

    # Every clue load bearing. The date is the one to watch: give it too thin a
    # day and it answers alone, which would make the other two decoration.
    for clue, expected in (
        ("role", README_WITHOUT_ROLE),
        ("department", README_WITHOUT_DEPARTMENT),
        ("start_date", README_WITHOUT_DATE),
    ):
        dropped = sorted_by_start(connection, without(clue))
        require(
            len(dropped) == expected
            and any(name == CULPRIT_NAME for name, _ in dropped),
            f"dropping {clue} should leave {expected} people including the"
            f" culprit, got {len(dropped)}; at one that clue is carrying the"
            " whole query and the other two are decoration",
        )

    # The second road in, for a player who never works the date out: drop it,
    # sort the eleven IT juniors and read the top row. It has to agree with the
    # intended solution and it has to have a unique top row.
    by_sort = sorted_by_start(connection, SORT_CLUES)
    require(
        len(by_sort) == README_IT_JUNIORS
        and by_sort[0] == (CULPRIT_NAME, CULPRIT_START),
        f"sorting the {README_IT_JUNIORS} IT juniors should top out at"
        f" {CULPRIT_NAME}, got {by_sort[:2]}",
    )
    require(
        by_sort[0][1] > by_sort[1][1],
        "the culprit ties with another IT junior for the newest start date, so"
        " the top row is whichever one the engine happens to return first",
    )
    require(
        by_sort[1][1] == NEAR_MISS_START,
        f"the second row should be the near miss on {NEAR_MISS_START}, got"
        f" {by_sort[1]}",
    )

    # And every wrong sort tops out at somebody innocent. Without a LIMIT a
    # player reads the first row whatever they typed, so a wrong query that
    # returned the culprit first would be a wrong query that worked.
    for clues, label, expected in (
        ((("department", CLUE_DEPARTMENT),),
         f"everybody in {CLUE_DEPARTMENT}", README_ABOVE_HIM_IN_IT),
        ((("role", CLUE_ROLE),),
         f"every {CLUE_ROLE}", README_ABOVE_HIM_AMONG_JUNIORS),
        ((), "the whole payroll", README_ABOVE_HIM_ON_THE_PAYROLL),
    ):
        rows = sorted_by_start(connection, clues)
        above = strictly_newer(rows, CULPRIT_START)
        require(
            above == expected and above > 0,
            f"sorting {label} by start date should put {expected} people"
            f" strictly above the culprit, found {above}; at zero the top row"
            " is his and that wrong query works",
        )

    # The intern is the trap for reading "the new kid" as a job title. He has
    # to be a real person in IT who really did start that week.
    interns = sorted_by_start(connection, (
        ("department", CLUE_DEPARTMENT),
        ("role", "Intern"),
    ))
    require(
        interns[0][0] == INTERN_NAME and interns[0][1] == NEWER_START,
        f"reading the clue as the intern should top out at {INTERN_NAME} on"
        f" {NEWER_START}, got {interns[0]}",
    )

    # Single clue counts, and the two October days.
    for emp_property, value, expected in (
        ("department", CLUE_DEPARTMENT, IT_TOTAL),
        ("role", CLUE_ROLE, JUNIOR_TOTAL),
        ("start_date", CULPRIT_START, README_ON_HIS_OWN_DAY),
        ("start_date", NEWER_START, NEWER_TOTAL),
    ):
        found = count(connection, f"""
            SELECT COUNT(*) FROM employees
            WHERE emp_property = '{emp_property}' AND value = '{value}'
        """)
        require(
            found == expected,
            f"{emp_property} = '{value}' should match {expected} employees,"
            f" got {found}",
        )

    or_filter = (f"value = '{CLUE_DEPARTMENT}' OR value = '{CLUE_ROLE}'"
                 f" OR value = '{CULPRIT_START}'")
    or_rows = count(connection, f"""
        SELECT COUNT(*) FROM employees WHERE {or_filter}
    """)
    or_people = count(connection, f"""
        SELECT COUNT(DISTINCT emp_code) FROM employees WHERE {or_filter}
    """)
    require(
        or_rows == README_OR_ROWS and or_people == README_OR_PEOPLE,
        f"the README quotes {README_OR_ROWS} rows over {README_OR_PEOPLE}"
        f" people for the three clues ORed together, found {or_rows} over"
        f" {or_people}",
    )
    # That the OR total is exactly the sum of the two also proves both clue
    # values are unambiguous: no name is 'Junior' and no other property takes
    # the value 'IT'. The evidence is fair even written without emp_property.
    require(
        or_rows == IT_TOTAL + JUNIOR_TOTAL + CULPRIT_DAY_TOTAL,
        "one of the clue values is also some other property's value, which"
        " makes the evidence ambiguous",
    )

    # The hazard that makes the point anyway: one value in the table is a
    # birthday to one person and a first day to another.
    collisions = [
        (emp_code, emp_property) for emp_code, emp_property in connection.execute(
            f"SELECT emp_code, emp_property FROM employees WHERE value ="
            f" '{COLLIDING_VALUE}' ORDER BY emp_property"
        )
    ]
    require(
        len(collisions) == COLLISION_ROWS
        and {emp_property for _, emp_property in collisions}
            == {"date_of_birth", "start_date"},
        f"'{COLLIDING_VALUE}' should be one person's date_of_birth and"
        f" another's start_date, found {collisions}",
    )

    # None of the orderings a player can sort by points at the culprit.
    # Sorting by the staff code has to tell a player nothing. The codes are
    # drawn rather than counted, so this is about proving the draw came out
    # that way: the culprit sits well inside the ordering and October's
    # starters are scattered right across it.
    codes_in_order = [row[0] for row in connection.execute(
        "SELECT DISTINCT emp_code FROM employees ORDER BY emp_code"
    )]
    rank = {code: index for index, code in enumerate(codes_in_order)}
    october_ranks = sorted(
        rank[row[0]] for row in connection.execute(f"""
            SELECT emp_code FROM employees
            WHERE emp_property = 'start_date' AND value >= '{NEAR_MISS_START}'
        """)
    )
    span = october_ranks[-1] - october_ranks[0]
    require(
        span >= README_OCTOBER_CODE_SPAN,
        f"October's starters cover only {span} of the code ordering, which is"
        " clustered enough for ORDER BY emp_code to find the newest hires",
    )
    culprit_emp_code = count(connection, f"""
        SELECT c1.emp_code FROM employees c1
        JOIN employees c2 ON c2.emp_code = c1.emp_code
                         AND c2.emp_property = 'last_name'
        WHERE c1.emp_property = 'first_name'
          AND c1.value || ' ' || c2.value = '{CULPRIT_NAME}'
    """)
    margin = EMPLOYEE_COUNT // 5
    require(
        margin <= rank[culprit_emp_code] <= EMPLOYEE_COUNT - 1 - margin,
        f"the culprit's code {culprit_emp_code} sorts at position"
        f" {rank[culprit_emp_code]} of {EMPLOYEE_COUNT}, within {margin} of an"
        " end of the ordering, which makes it conspicuous",
    )

    younger = count(connection, f"""
        SELECT COUNT(*) FROM employees
        WHERE emp_property = 'date_of_birth' AND value > '{CULPRIT_BIRTH}'
    """)
    require(
        younger == README_YOUNGER_THAN_CULPRIT and younger > 0,
        f"the README quotes {README_YOUNGER_THAN_CULPRIT} employees younger"
        f" than the culprit, found {younger}; at zero, ORDER BY date_of_birth"
        " DESC would hand over the answer",
    )

    newest = count(connection, """
        SELECT MAX(value) FROM employees WHERE emp_property = 'start_date'
    """)
    require(
        newest == NEWER_START,
        f"the Friday intake of {NEWER_START} should be the newest thing in the"
        f" table, found {newest}; the culprit must never hold it",
    )

    # The shape of the store itself: one row per property per person, nothing
    # missing, nothing extra.
    rows = count(connection, "SELECT COUNT(*) FROM employees")
    require(
        rows == README_ROW_COUNT,
        f"the README quotes {README_ROW_COUNT} rows, found {rows}",
    )
    require(
        count(connection, "SELECT COUNT(DISTINCT emp_code) FROM employees")
        == EMPLOYEE_COUNT,
        f"the table should hold {EMPLOYEE_COUNT} employees",
    )
    require(
        count(connection, f"""
            SELECT COUNT(*) FROM (
                SELECT emp_code FROM employees GROUP BY emp_code
                HAVING COUNT(*) <> {len(PROPERTIES)}
                    OR COUNT(DISTINCT emp_property) <> {len(PROPERTIES)}
            )
        """) == 0,
        f"every employee needs exactly {len(PROPERTIES)} rows, one per property"
        " -- an incomplete record would drop out of the player's pivot",
    )
    properties = {row[0] for row in connection.execute(
        "SELECT DISTINCT emp_property FROM employees"
    )}
    require(
        properties == set(PROPERTIES),
        f"the store holds properties {sorted(properties)}, expected"
        f" {sorted(PROPERTIES)}",
    )
    codes = {row[0] for row in connection.execute(
        "SELECT DISTINCT emp_code FROM employees"
    )}
    require(
        len(codes) == EMPLOYEE_COUNT,
        f"the store should hold {EMPLOYEE_COUNT} distinct staff codes, found"
        f" {len(codes)}",
    )
    require(
        all(len(code) == EMP_CODE_LETTERS + EMP_CODE_DIGITS
            and code[:EMP_CODE_LETTERS].isalpha()
            and code[:EMP_CODE_LETTERS].isupper()
            and code[EMP_CODE_LETTERS:].isdigit()
            for code in codes),
        "a staff code is not four capitals followed by four digits",
    )
    # The Int32 ceiling the game reads an INTEGER column into is the trap that
    # made two other cases here unplayable. It cannot bite this one: every
    # column in the table is TEXT, staff code included.
    require(
        not [row for row in connection.execute("PRAGMA table_info(employees)")
             if row[2].upper() != "TEXT"],
        "a column in employees is not TEXT, which puts the Int32 ceiling back"
        " in play",
    )

    # Values. Departments and roles come from the two fixed vocabularies, dates
    # are eight character calendar dates, and no two people share a full name.
    for emp_property, vocabulary in (("department", DEPARTMENTS), ("role", ROLES)):
        found = {row[0] for row in connection.execute(
            f"SELECT DISTINCT value FROM employees WHERE emp_property = '{emp_property}'"
        )}
        require(
            found <= set(vocabulary),
            f"{emp_property} holds {sorted(found - set(vocabulary))}, which is"
            " not in its vocabulary",
        )
    names = [row[0] for row in connection.execute("""
        SELECT c1.value || ' ' || c2.value FROM employees c1
        JOIN employees c2 ON c2.emp_code = c1.emp_code AND c2.emp_property = 'last_name'
        WHERE c1.emp_property = 'first_name'
    """)]
    require(
        len(set(names)) == EMPLOYEE_COUNT,
        "two employees share a full name, which makes the arrest ambiguous",
    )
    require(
        CULPRIT_NAME in names and len(CULPRIT_NAME) <= 17,
        f"the arrest form takes 17 characters; '{CULPRIT_NAME}' is"
        f" {len(CULPRIT_NAME)}",
    )

    ages = []
    for emp_code, in connection.execute("SELECT DISTINCT emp_code FROM employees"):
        born, started = (
            count(connection, f"""
                SELECT value FROM employees
                WHERE emp_code = '{emp_code}' AND emp_property = '{emp_property}'
            """)
            for emp_property in ("date_of_birth", "start_date")
        )
        for value in (born, started):
            require(
                len(value) == 8 and value.isdigit(),
                f"{value} is not an eight character stamped date",
            )
        birthday, first_day = as_date(born), as_date(started) # raise if not real dates
        age_at_hire = (first_day - birthday).days // 365
        require(
            MIN_AGE_AT_HIRE <= age_at_hire <= MAX_AGE_AT_HIRE,
            f"employee {emp_code} started at {age_at_hire}, which is outside"
            f" {MIN_AGE_AT_HIRE} to {MAX_AGE_AT_HIRE}",
        )
        require(
            first_day.weekday() < 5,
            f"employee {emp_code} started on a {first_day.strftime('%A')}",
        )
        require(
            FOUNDED <= first_day <= INCIDENT,
            f"employee {emp_code} started outside the company's history",
        )
        ages.append((TODAY - birthday).days // 365)
    require(
        max(ages) <= MAX_AGE_NOW,
        f"somebody on the payroll is {max(ages)}, over the {MAX_AGE_NOW} cap",
    )

    print(f"Wrote {DATABASE_PATH}")
    print(f"Culprit: {CULPRIT_NAME}, emp_code {culprit_emp_code}, {CLUE_DEPARTMENT}"
          f" {CLUE_ROLE}, started {CULPRIT_START}")
    print(f"{EMPLOYEE_COUNT} employees x {len(PROPERTIES)} properties = {rows} rows")
    print(f"The three clues name {len(solution)}: {solution[0]}")
    print(f"Without the role {README_WITHOUT_ROLE}, without the department"
          f" {README_WITHOUT_DEPARTMENT}, without the date {README_WITHOUT_DATE}")
    print(f"{README_ON_HIS_OWN_DAY} started his Thursday, {NEWER_TOTAL} the"
          f" Friday after, {README_IT_JUNIORS} IT {CLUE_ROLE}s all told")
    print(f"Dropping the date and sorting still tops out at {by_sort[0]},"
          f" with {by_sort[1]} behind it")
    print(f"Sorting by start date puts {README_ABOVE_HIM_IN_IT} above him in"
          f" {CLUE_DEPARTMENT}, {README_ABOVE_HIM_AMONG_JUNIORS} above him among"
          f" {CLUE_ROLE}s, {README_ABOVE_HIM_ON_THE_PAYROLL} above him overall")
    print(f"'{CLUE_DEPARTMENT}' matches {IT_TOTAL}, '{CLUE_ROLE}' {JUNIOR_TOTAL};"
          f" the three ORed together {or_rows} rows over {or_people} people")
    print(f"Reading the clue as the intern tops out at {INTERN_NAME}")
    print(f"October's emp_codes span {span}; {younger} employees are younger"
          " than the culprit")

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
