"""
Generates the SQLite database for the custom case "Where Are You?".

The player gets a photograph of a house -- single storey, red roof, white
walls, black door, brown fence -- whose number plate is torn so that only the
leading "3" and the trailing "13" are readable, plus a notice saying one
property in the neighbourhood never paid its annual common-area fee. The answer
is the owner of the one house that matches the photograph AND has no row in
`fee_payments`.

As in `halloween.py`, the difficulty lives in the data distribution rather than
in any rule engine:
  * five houses match the photograph exactly and only one of them is unpaid, so
    the description alone cannot name the culprit;
  * ~30 houses are unpaid, so the ledger alone cannot name the culprit either;
  * every clue is load bearing -- for each of the six clues there is an unpaid
    house matching the other five, so dropping any clue returns more than one
    row.

`verify()` asserts all of the above and runs automatically, so the script
refuses to leave an unsolvable database behind.

Run from anywhere:  python3 "Sources/Where Are You/where.py"
"""
import random
import sqlite3
import sys
from pathlib import Path
from typing import Iterable, Tuple

# db_utils and its name lists come from the upstream workshop kit, which is
# vendored as a submodule and deliberately left untouched -- so reach into it
# rather than copying it out.
REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "dbd-workshop" / "Scripts"))

from db_utils import create_populate_table, database_connection, get_random_name

DATABASE_NAME = "where_are_you"
DATABASE_PATH = REPO / "Where Are You" / DATABASE_NAME # written straight into the case folder
CULPRIT_NAME = "Dodge Hollings"
HOUSEHOLD_COUNT = 300 # Number of rows in `households` table
ANNUAL_FEE = 2400 # The common-area fee every household owes
UNPAID_TARGET = 32 # Households with no row in `fee_payments`, culprit included

# The photograph. Each entry is a clue the player has to turn into SQL.
NUMBER_PATTERN = "3%13"
CULPRIT_HOUSE = "34713"
CULPRIT_FLOORS = 1
CULPRIT_ROOF = "Red"
CULPRIT_WALL = "White"
CULPRIT_DOOR = "Black"
CULPRIT_FENCE = "Brown"

# Houses matching the photograph exactly, culprit included. Fixing them all at
# five digits means a player who infers the plate's length from the photo still
# cannot narrow the set any further than LIKE '3%13' does.
TWIN_HOUSES = ["31013", "32513", "36713", "39113"]
DESCRIPTION_MATCHES = 1 + len(TWIN_HOUSES)

# One unpaid house per clue, matching the other five clues. `house_number`'s
# decoy starts with 3 and contains 13 without ending in it, so LIKE '3%13%'
# returns two rows.
DECOY_HOUSES = {
    "house_number": ("31347", {}),
    "floors": ("33213", {"floors": 2}),
    "roof_color": ("34213", {"roof_color": "Slate"}),
    "wall_color": ("35113", {"wall_color": "Beige"}),
    "door_color": ("37013", {"door_color": "Red"}),
    "fence_color": ("38613", {"fence_color": "White"}),
}

ROOF_COLORS = ["Red", "Grey", "Brown", "Green", "Slate", "Terracotta"]
WALL_COLORS = ["White", "Beige", "Cream", "Grey", "Blue", "Yellow", "Pink"]
DOOR_COLORS = ["Black", "White", "Brown", "Red", "Blue", "Green"]
FENCE_COLORS = ["Brown", "White", "Black", "Green", "Grey"]
FLOOR_OPTIONS = [1, 1, 1, 2, 2, 3]

CLUES = [
    ("house_number LIKE ?", NUMBER_PATTERN),
    ("floors = ?", CULPRIT_FLOORS),
    ("roof_color = ?", CULPRIT_ROOF),
    ("wall_color = ?", CULPRIT_WALL),
    ("door_color = ?", CULPRIT_DOOR),
    ("fence_color = ?", CULPRIT_FENCE),
]
UNPAID_CLAUSE = "house_number NOT IN (SELECT house_number FROM fee_payments)"

@database_connection(str(DATABASE_PATH))
def create_tables(connection: sqlite3.Connection) -> None:
    household_rows, unpaid = generate_households()
    payment_rows = generate_payments(household_rows, unpaid)
    create_households_table(connection, household_rows)
    create_fee_payments_table(connection, payment_rows)
    verify(connection)

def generate_households() -> Tuple[list, set]:
    """
    Builds the `households` rows.
    Returns a tuple of...
        1: the rows, sorted by house number
        2: the set of house numbers with no fee payment
    """
    rows = []
    taken_numbers = set()
    taken_owners = {CULPRIT_NAME}

    # The culprit and the four houses that look exactly like it.
    rows.append(make_house(CULPRIT_HOUSE, CULPRIT_NAME))
    taken_numbers.add(CULPRIT_HOUSE)
    for house_number in TWIN_HOUSES:
        rows.append(make_house(house_number, next_owner(taken_owners)))
        taken_numbers.add(house_number)

    # One near miss per clue.
    decoy_numbers = set()
    for house_number, overrides in DECOY_HOUSES.values():
        rows.append(make_house(house_number, next_owner(taken_owners), **overrides))
        taken_numbers.add(house_number)
        decoy_numbers.add(house_number)

    # Everyone else. Keeping random houses off the 3...13 pattern is what makes
    # the five description matches above exact.
    while len(rows) < HOUSEHOLD_COUNT:
        house_number = next_house_number(taken_numbers)
        taken_numbers.add(house_number)
        rows.append({
            "house_number": house_number,
            "owner": next_owner(taken_owners),
            "floors": random.choice(FLOOR_OPTIONS),
            "roof_color": random.choice(ROOF_COLORS),
            "wall_color": random.choice(WALL_COLORS),
            "door_color": random.choice(DOOR_COLORS),
            "fence_color": random.choice(FENCE_COLORS),
        })

    # The culprit and every decoy must be unpaid; the twins must have paid, or
    # the final query would return more than one owner.
    unpaid = {CULPRIT_HOUSE} | decoy_numbers
    reserved = taken_numbers - set(TWIN_HOUSES) - unpaid
    unpaid |= set(random.sample(sorted(reserved), UNPAID_TARGET - len(unpaid)))

    rows.sort(key=lambda row: int(row["house_number"]))
    return rows, unpaid

def make_house(house_number: str, owner: str, **overrides) -> dict:
    "Builds a house matching the photograph, less any overridden clue."
    house = {
        "house_number": house_number,
        "owner": owner,
        "floors": CULPRIT_FLOORS,
        "roof_color": CULPRIT_ROOF,
        "wall_color": CULPRIT_WALL,
        "door_color": CULPRIT_DOOR,
        "fence_color": CULPRIT_FENCE,
    }
    house.update(overrides)
    return house

def next_house_number(taken: set) -> str:
    "A unique 3-to-5 digit house number that does not match the plate."
    while True:
        digits = random.randint(3, 5)
        house_number = str(random.randint(10 ** (digits - 1), 10 ** digits - 1))
        if house_number not in taken and not matches_plate(house_number):
            return house_number

def matches_plate(house_number: str) -> bool:
    "Mirrors LIKE '3%13' so random houses can be kept off the pattern."
    return house_number.startswith("3") and house_number.endswith("13")

def next_owner(taken: set) -> str:
    "A unique owner name, so the arrest is never ambiguous."
    while True:
        first_name, last_name = get_random_name()
        owner = f"{first_name} {last_name}"
        if owner not in taken:
            taken.add(owner)
            return owner

def generate_payments(household_rows: Iterable[dict], unpaid: set) -> list:
    "One row per household that paid this year's fee."
    payment_rows = []
    for row in household_rows:
        if row["house_number"] in unpaid:
            continue
        payment_rows.append({
            "house_number": row["house_number"],
            "payment_date": f"2025-{random.randint(1, 3):02d}-{random.randint(1, 28):02d}",
            "amount": ANNUAL_FEE,
        })
    return payment_rows

def create_households_table(connection: sqlite3.Connection, household_rows: list) -> None:
    table_name = "households"
    columns = {
        "house_number": "TEXT",
        "owner": "TEXT",
        "floors": "INTEGER",
        "roof_color": "TEXT",
        "wall_color": "TEXT",
        "door_color": "TEXT",
        "fence_color": "TEXT",
    }
    create_populate_table(connection, table_name, columns, household_rows)

def create_fee_payments_table(connection: sqlite3.Connection, payment_rows: list) -> None:
    table_name = "fee_payments"
    columns = {
        "house_number": "TEXT",
        "payment_date": "TEXT",
        "amount": "INTEGER",
    }
    create_populate_table(connection, table_name, columns, payment_rows)

def solve(connection: sqlite3.Connection, skip: int = None, unpaid: bool = True) -> list:
    "Runs the intended solution, optionally dropping one clue."
    clauses = []
    params = []
    for index, (fragment, value) in enumerate(CLUES):
        if index == skip:
            continue
        clauses.append(fragment)
        params.append(value)
    if unpaid:
        clauses.append(UNPAID_CLAUSE)
    query = f"SELECT owner FROM households WHERE {' AND '.join(clauses)}"
    return [row[0] for row in connection.execute(query, params)]

def verify(connection: sqlite3.Connection) -> None:
    "Fails loudly rather than leaving an unsolvable case behind."
    solution = solve(connection)
    require(
        solution == [CULPRIT_NAME],
        f"the full solution should name only {CULPRIT_NAME}, got {solution}",
    )

    described = solve(connection, unpaid=False)
    require(
        len(described) == DESCRIPTION_MATCHES,
        f"the photograph should match {DESCRIPTION_MATCHES} houses, got {len(described)}",
    )

    unpaid_count = count(connection, f"SELECT COUNT(*) FROM households WHERE {UNPAID_CLAUSE}")
    require(
        unpaid_count == UNPAID_TARGET,
        f"expected {UNPAID_TARGET} unpaid households, got {unpaid_count}",
    )

    for index, (fragment, _) in enumerate(CLUES):
        partial = solve(connection, skip=index)
        require(
            len(partial) > 1,
            f"dropping `{fragment}` should leave more than one suspect, got {partial}",
        )

    require(
        count(connection, "SELECT COUNT(DISTINCT owner) FROM households") == HOUSEHOLD_COUNT,
        "owner names are not unique",
    )
    require(
        count(connection, "SELECT COUNT(DISTINCT house_number) FROM households") == HOUSEHOLD_COUNT,
        "house numbers are not unique",
    )

    print(f"Wrote {DATABASE_PATH}")
    print(f"Culprit: {CULPRIT_NAME} at {CULPRIT_HOUSE}")
    print(f"{HOUSEHOLD_COUNT} households, {unpaid_count} of them unpaid")
    print(f"{DESCRIPTION_MATCHES} houses match the photograph, 1 of them unpaid")
    print("Every clue is load bearing.")

def count(connection: sqlite3.Connection, query: str) -> int:
    return connection.execute(query).fetchone()[0]

def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)

def main() -> None:
    # CREATE TABLE IF NOT EXISTS plus INSERT would append to an existing file,
    # so start from scratch on every run.
    DATABASE_PATH.unlink(missing_ok=True)
    create_tables()

if __name__ == "__main__":
    main()
