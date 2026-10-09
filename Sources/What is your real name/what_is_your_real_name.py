"""
Generates the SQLite database for the custom case "What is your real name?".

A caller recognised Allison Burgers -- the general who emptied a treasury and
ran, ten years ago this autumn -- queueing for a bus in this city. He has been
here the whole time, and he has filed a legal change of name in every one of
those years, so the name on the wanted file is nine names out of date.

The civil registry cannot answer the question. `residents` holds one name per
person and the clerk overwrites it in place, so a former name leaves no trace
there; `name_changes` keeps the old name, the new one and the year it was
stamped, and *no person number at all* -- Records has never issued one. The
only road from the wanted file to the man is to walk the chain one year at a
time, from 'Allison Burgers' in 2017 through to 2026:

    SELECT c10.new_name
    FROM name_changes c1
    JOIN name_changes c2  ON c2.old_name  = c1.new_name  AND c2.year  = 2018
    ...
    JOIN name_changes c10 ON c10.old_name = c9.new_name  AND c10.year = 2026
    WHERE c1.old_name = 'Allison Burgers' AND c1.year = 2017;

Ten separate one-table queries walk the same chain, which is what keeps the
case solvable even if the in-game console balks at a ten-way self join. The
years are written out as literals rather than `c1.year + 1`, because
arithmetic inside an expression has not been tried in that console yet.

The difficulty lives in the data distribution, as in the other cases here, and
every shortcut points somewhere other than the culprit:

  * `old_name = 'Allison Burgers'` returns *two* rows. A protester legally took
    the dictator's name in 2019 and dropped it again in 2021, and his own
    chain -- 2021, 2023, 2026, never two years running -- ends at a living
    resident. Starting on the wrong row arrests an innocent man rather than
    returning nothing;
  * the culprit's own name after 2024, 'Kip Clearofdoors', has an onward
    change in 2026 as well as his in 2025, because somebody else copied the
    same door sign. A player who assumes the last change must be the one
    stamped in 2026 arrests 'Owt Tolunch';
  * two more names on the chain are shared the same way, so the chain only
    stays single-file if every step insists on the next year;
  * asking the question structurally -- which chain runs through all ten years
    -- accuses two, because a sign painter's apprentice renamed himself every
    year as well, from a different starting name;
  * the chain-end shortcut (`year = 2026` and a new name that is nobody's old
    name) accuses twenty-four;
  * picking the daft name out of the column by eye accuses one of thirteen.
    Renaming yourself after a sign is a fad in this city, and the change log
    is full of it.

`verify()` asserts all of the above and runs automatically, so the script
refuses to leave an unsolvable database behind.

Run from anywhere:  python3 "Sources/What is your real name/what_is_your_real_name.py"
"""
import random
import sqlite3
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

# db_utils and its name lists come from the upstream workshop kit, which is
# vendored as a submodule and deliberately left untouched -- so reach into it
# rather than copying it out.
REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "dbd-workshop" / "Scripts"))

from db_utils import create_populate_table, database_connection, get_random_name

DATABASE_NAME = "civil_registry"
DATABASE_PATH = REPO / "What is your real name" / DATABASE_NAME # into the case folder

SEED = 20261008 # fixed, so a rebuild reproduces the shipped case exactly --
                # the evidence artwork and README quote figures from this data

TODAY = date(2026, 10, 8)
FLED_YEAR = 2016          # the year on the wanted file
LOG_FIRST_YEAR = 2014     # the registry's log starts here; it predates him, so
                          # the span of the log says nothing about him
LOG_LAST_YEAR = 2026

# The name on the ten-year-old wanted file, and the whole of what it is good
# for: the registry holds nothing that can be compared against a ten-year-old
# description, so the name and the year he started are the only way in.
WANTED_NAME = "Allison Burgers"

# The chain, as (year the change was stamped, the name it gave him). He copies
# each new name off whatever he has been reading: 2025 is the year he tried to
# go straight, which is why the last change alters only the surname.
CHAIN: Tuple[Tuple[int, str], ...] = (
    (2017, "Way Owt"),
    (2018, "Ladiz Washroom"),
    (2019, "Emplyes Mustwashhands"),
    (2020, "Noah Diving"),
    (2021, "Mynd Thegap"),
    (2022, "Dee Tourahead"),
    (2023, "Fyre Exitonly"),
    (2024, "Kip Clearofdoors"),
    (2025, "Max Wellhouse"),
    (2026, "Max Imumoccupancy"),
)
CULPRIT_NAME = CHAIN[-1][1]
CULPRIT_NAMES: Tuple[str, ...] = (WANTED_NAME,) + tuple(name for _, name in CHAIN)
CULPRIT_YEARS: Tuple[int, ...] = tuple(year for year, _ in CHAIN)

# Pinned rather than drawn, because the arrest warrant and the case README
# quote them.
CULPRIT_DISTRICT = "Kettleford"
CULPRIT_OCCUPATION = "Night porter"

# The protester. He took the dictator's name in 2019 as a stunt, dropped it in
# 2021, and has renamed himself twice since -- never two years running, which
# is the whole of what separates his chain from the culprit's. It ends at a
# living resident, so starting on his row arrests somebody innocent.
HOAXER: Dict[str, Sequence] = {
    "names": ("Dennis Follingsby", WANTED_NAME, "Noah Loitering",
              "Plez Kyuhere", "Dunn Otdisturb"),
    "years": (2019, 2021, 2023, 2026),
}

# The sign painter's apprentice, who renamed himself in every one of the same
# ten years from a different starting name. He is why asking the question
# structurally -- whose chain runs 2017 through 2026 -- accuses two people, and
# why the wanted file's name is the only way in.
UNDERSTUDY: Dict[str, Sequence] = {
    "names": ("Harold Stennick", "Noah Xit", "Fyre Assemblypoint",
              "Loss Tproperty", "Kwy Etplease", "Nowe Serving",
              "Tay Katicket", "Stan Dontheright", "Slip Erywhenwet",
              "Lo Bridge", "Gon Fishing"),
    "years": (2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026),
}

# Three citizens who copied the same signs he did, so three names on his chain
# have two onward changes instead of one. Each leaves the chain in a year that
# is not his next, and each ends at a living resident, so a step taken on the
# wrong row accuses somebody. The third is the sharpest: 'Kip Clearofdoors'
# leaves for 'Owt Tolunch' in 2026, the year a player expects the last change
# to be stamped in, while the culprit left it in 2025.
TWINS: Tuple[Dict[str, Sequence], ...] = (
    {"names": ("Marcus Oyle", "Ladiz Washroom", "Vay Cant"), "years": (2016, 2021)},
    {"names": ("Ingrid Pollasky", "Noah Diving", "Eng Aged"), "years": (2018, 2023)},
    {"names": ("Trevor Lundqvist", "Kip Clearofdoors", "Owt Tolunch"),
     "years": (2022, 2026)},
)
TWIN_NAMES = tuple(twin["names"][1] for twin in TWINS)

# Residents whose current name is as daft as the culprit's, so that picking the
# odd one out of the column by eye arrests somebody innocent rather than him.
SIGN_RESIDENTS = ("Lyft Outofservice", "Noah Smoking", "Myn Dyourhead",
                  "Wett Paynt", "Platt Form", "Speed Limit", "Bay Parking")

# Everybody called Max, so that a player who gets as far as 2025 and stops
# still has nine residents to choose between.
MAX_FIRST_NAME = "Max"
MAX_RESIDENT_COUNT = 9 # including the culprit

# The population. Everybody who never filed a change is a resident under the
# name they were born with; everybody who did is a resident under the last name
# in their chain, and every name they left behind exists only in the log.
PLAIN_COUNT = 380
CHANGER_COUNT = 240
ORDINARY_CHANGES = (1, 4) # how many times an ordinary changer renamed themself

# Ordinary changers whose last change is stamped in 2026. Constructed rather
# than drawn, so the chain-end shortcut's count is fixed and the artwork can
# quote it.
ORDINARY_END_2026 = 20
SCATTERED_SIGN_COUNT = 20 # ordinary changers who took a sign name, so the fad
                          # the caller describes is visible in the log and the
                          # culprit's chain is not the only daft one in it

DISTRICTS = ("Kettleford", "Brayhill", "Ostmarket", "Veldt Row", "Canal Side",
             "Thurnby", "Old Quay", "Marsden Vale")
OCCUPATIONS = ("Night porter", "Bus driver", "Baker", "Locksmith", "Welder",
               "Shelf stacker", "Sign painter", "Dog walker", "Clerk",
               "Barber", "Caretaker", "Gardener", "Taxi driver", "Butcher",
               "Plumber", "Courier", "Waiter", "Roofer")
OFFICES = ("Central Registry", "North Annexe", "Harbour Office", "Civic Hall",
           "Veldt Row Office", "Thurnby Sub-office")
CULPRIT_OFFICE_SPREAD = 4 # he never filed twice in the same place twice over;
                          # spread_culprit_offices() redraws until his ten
                          # changes touch at least this many counters, so
                          # grouping the log by office finds no cluster

RESIDENT_DIGITS = 6
CHANGE_FIRST_NO = 1000000 # the log's numbers climb with the year and carry
CHANGE_STEP = (3, 40)     # nothing else, so sorting by them teaches nothing

# The city's stock of sign names, which the fad draws on. Deliberately large:
# the culprit's ten have to sit in a crowd of them.
SIGN_POOL = (
    "Noe Parking", "Wayt Here", "Pusch Topen", "Pull Toclose",
    "Cau Tionwetfloor", "Mopp Inprogress", "Kee Poffthegrass", "Giv Veway",
    "Kip Pleft", "Slo Downe", "Dea Dend", "Wan Neway", "Wat Chyourstep",
    "Otto Fordor", "Fyre Dorkeepshut", "Bee Wareofthedog", "Pryv Ateproperty",
    "Otho Risedpersonnel", "Ryng Forservice", "Clo Sedforlunch",
    "Bak Infyveminutes", "Pusch Bartopen", "Noah Throughroad",
    "Toy Letsdownstairs", "Dan Gerhighvoltage", "Caut Ionhotsurface",
    "Rez Ervedforstaff", "Del Iveriesatrear", "Fass Tenseatbelts",
    "Em Ergencyexit", "Sol Dout", "Pull Heere", "Han Dlewithcare",
    "Thys Sideup", "Fra Gyle", "Kip Refrigerated", "Bess Tbefore",
    "Shay Kwell", "Fla Mmable", "Noah Vacancies", "Plez Wayt",
    "Mynd Thedoors", "Furs Tayd", "Noah Foodordrink", "Unda Newmanagement",
    "Sayl Nowon", "Cash Honly", "Exa Ctchange", "Staf Fonly", "Exi Tonly",
    "Noah Ntry", "Lo Dingbay", "Kip Gateshut", "Mynd Yourbag",
    "Noah Ballgames", "Plez Shutthegate", "Wayt Forgreen", "Loo Kbothways",
    "Noah Cycling", "Keap Outt", "Siy Lencepleas", "Stop Herre",
    "Noah Smokingarea", "Lif Toutoforder", "Beware Thestep",
)

# Counts the construction fixes, kept here so that changing one and re-running
# is safe: verify() reads them rather than re-deriving them.
RESIDENT_COUNT = (PLAIN_COUNT + CHANGER_COUNT + 1 # the culprit
                  + 1 + 1 + len(TWINS))           # hoaxer, understudy, twins
END_2026_TOTAL = ORDINARY_END_2026 + 4 # culprit, hoaxer, understudy, third twin
SIGN_RESIDENT_TOTAL = (1                     # the culprit
                       + len(SIGN_RESIDENTS)
                       + 1 + 1 + len(TWINS)) # hoaxer, understudy, twins

# An INTEGER column is read into an Int32 and a larger value fails the case
# load outright, so every number this script generates is held under it.
INT32_MAX = 2147483647

# Draw-dependent, so pinned here and asserted: a rebuild that moves one fails
# rather than quietly making the README lie.
README_HOAXER_DISTRICT = "Thurnby"    # the protester's registry row, quoted in
README_HOAXER_OCCUPATION = "Barber"   # the case README as the man a wrong first
                                      # step arrests
README_CULPRIT_OFFICES = 5            # counters his ten changes touch
README_CULPRIT_RESIDENT_NO = 688263
README_CHANGE_ROWS = 627
README_SIGN_NAMES_IN_LOG = (len(CULPRIT_NAMES) - 2 # his nine; 2025 is not one
                            + 3                    # the hoaxer's
                            + 10                   # the understudy's
                            + len(TWINS)           # the twins' own finals
                            + SCATTERED_SIGN_COUNT) # the fad at large, the
                                                    # seven forced finals among
                                                    # them

@database_connection(str(DATABASE_PATH))
def create_tables(connection: sqlite3.Connection) -> None:
    people = build_people()
    resident_rows = build_residents(people)
    change_rows = build_changes(people)
    create_residents_table(connection, resident_rows)
    create_changes_table(connection, change_rows)
    verify(connection)

def build_people() -> List[dict]:
    """
    Everybody in the city, as the registry refuses to record them: a list of
    every name they have held, oldest first, and the year each change was
    stamped. `names[-1]` is what they answer to now and the only one the
    `residents` table will ever see.

    The parts people play live here and reach the database only as rows in the
    log, which is what makes the case turn on the chain rather than on a
    column.
    """
    taken = {WANTED_NAME, CULPRIT_NAME}
    for role in (HOAXER, UNDERSTUDY, *TWINS):
        taken.update(role["names"])
    taken.update(CULPRIT_NAMES)
    taken.update(SIGN_RESIDENTS)

    signs = [name for name in SIGN_POOL if name not in taken]
    random.shuffle(signs)

    people = [
        {"role": "culprit", "names": list(CULPRIT_NAMES),
         "years": list(CULPRIT_YEARS)},
        {"role": "hoaxer", "names": list(HOAXER["names"]),
         "years": list(HOAXER["years"])},
        {"role": "understudy", "names": list(UNDERSTUDY["names"]),
         "years": list(UNDERSTUDY["years"])},
    ]
    people += [{"role": "twin", "names": list(twin["names"]),
                "years": list(twin["years"])} for twin in TWINS]

    # The ordinary changers. Twenty of them end in 2026, which fixes the
    # chain-end shortcut's count; twenty take a sign name, which puts the fad
    # in the log; seven of those land on a sign name and stop, which is the
    # crowd the culprit's own daft name hides in.
    forced_finals = list(SIGN_RESIDENTS)
    change_counts = [random.randint(*ORDINARY_CHANGES)
                     for _ in range(CHANGER_COUNT)]
    ends_2026 = set(random.sample(range(CHANGER_COUNT), ORDINARY_END_2026))
    # A scattered sign name goes somewhere in the middle of a chain, so it ends
    # up in the log without putting a daft name in the registry -- which means
    # only people who renamed themselves more than once can carry one.
    middling = [index for index, changes in enumerate(change_counts)
                if changes >= 2]
    sign_users = set(random.sample(middling,
                                   SCATTERED_SIGN_COUNT - len(forced_finals)))
    final_slots = set(random.sample(
        sorted(set(range(CHANGER_COUNT)) - sign_users), len(forced_finals)))

    for index, changes in enumerate(change_counts):
        years = ordinary_years(changes, index in ends_2026)
        names = [unique_real_name(taken)]
        for _ in range(changes):
            names.append(unique_real_name(taken))
        if index in sign_users:
            names[random.randrange(1, len(names) - 1)] = take(signs, taken)
        if index in final_slots:
            names[-1] = forced_finals.pop()
        people.append({"role": "changer", "names": names, "years": years})

    # Everybody who never renamed themself. Eight of them are called Max, so
    # the player who stops at 2025 has nine people to choose between.
    for index in range(PLAIN_COUNT):
        if index < MAX_RESIDENT_COUNT - 1:
            name = unique_real_name(taken, first_name=MAX_FIRST_NAME)
        else:
            name = unique_real_name(taken)
        people.append({"role": "plain", "names": [name], "years": []})

    require(not forced_finals, "a forced sign-name resident was never placed")
    return people

def ordinary_years(changes: int, ends_2026: bool) -> List[int]:
    """
    The years an ordinary changer's renamings were stamped: distinct, in order,
    and inside the log. Nobody ordinary renames themself in consecutive years
    for ten years running -- that is the culprit's and the understudy's alone.
    """
    # Drawn out of the years before the last one, so that ending in 2026 is
    # something this function grants rather than something the draw stumbles
    # into: the chain-end shortcut's count has to be fixed, not sampled.
    years = sorted(random.sample(range(LOG_FIRST_YEAR, LOG_LAST_YEAR), changes))
    if ends_2026:
        years[-1] = LOG_LAST_YEAR
    return years

def unique_real_name(taken: set, first_name: str = "") -> str:
    "An ordinary name nobody in the city has held before."
    while True:
        drawn_first, last = get_random_name()
        first = first_name or drawn_first
        # `Max` is placed deliberately and counted, so never draw into it.
        if not first_name and first.startswith(MAX_FIRST_NAME):
            continue
        name = f"{first} {last}"
        if name in taken or " " not in name or name.count(" ") != 1:
            continue
        taken.add(name)
        return name

def take(pool: List[str], taken: set) -> str:
    "The next unused sign name."
    require(bool(pool), "the city has run out of signs to be named after")
    name = pool.pop()
    taken.add(name)
    return name

def build_residents(people: List[dict]) -> List[dict]:
    """
    One row per person, under the name they answer to now. The table has no
    former-name column and no person number: the clerk types the new name over
    the old one, which is the premise the whole case rests on.
    """
    numbers = unique_ids(len(people), RESIDENT_DIGITS)
    rows = []
    for number, person in zip(numbers, people):
        if person["role"] == "culprit":
            district, occupation = CULPRIT_DISTRICT, CULPRIT_OCCUPATION
        else:
            district = random.choice(DISTRICTS)
            occupation = random.choice(OCCUPATIONS)
        rows.append({
            "resident_no": number,
            "name": person["names"][-1],
            "district": district,
            "occupation": occupation,
        })
    # Sorted by registry number, so the man is not conspicuously first.
    rows.sort(key=lambda row: row["resident_no"])
    return rows

def build_changes(people: List[dict]) -> List[dict]:
    """
    The log, one row per renaming: the name given up, the name taken, the year
    it was stamped and the counter it was stamped at. No person number appears
    anywhere, which is why a chain can only be followed by name.
    """
    changes = []
    for person in people:
        offices = (spread_culprit_offices() if person["role"] == "culprit"
                   else [random.choice(OFFICES) for _ in person["years"]])
        for step, year in enumerate(person["years"]):
            changes.append({
                "old_name": person["names"][step],
                "new_name": person["names"][step + 1],
                "year": year,
                "office": offices[step],
            })

    # Numbers climb with the year and with nothing else, so the log reads in
    # order and sorting by it says nothing about who filed what.
    random.shuffle(changes)
    changes.sort(key=lambda row: row["year"])
    number = CHANGE_FIRST_NO
    for row in changes:
        number += random.randint(*CHANGE_STEP)
        row["change_no"] = number
    return changes

def spread_culprit_offices() -> List[str]:
    """
    Which counter he filed each change at. Redrawn until his ten touch enough
    different offices that grouping the log by office finds no cluster to pull
    on -- the same care `Spy Everywhere` takes over the culprit's dates.
    """
    while True:
        offices = [random.choice(OFFICES) for _ in CULPRIT_YEARS]
        if len(set(offices)) >= CULPRIT_OFFICE_SPREAD:
            return offices

def unique_ids(count: int, digits: int) -> List[int]:
    "Distinct numbers of a fixed width, in no particular order."
    return random.sample(range(10 ** (digits - 1), 10 ** digits), count)

def create_residents_table(connection: sqlite3.Connection,
                           rows: List[dict]) -> None:
    create_populate_table(connection, "residents", {
        "resident_no": "INTEGER",
        "name": "TEXT",
        "district": "TEXT",
        "occupation": "TEXT",
    }, rows)

def create_changes_table(connection: sqlite3.Connection,
                         rows: List[dict]) -> None:
    create_populate_table(connection, "name_changes", {
        "change_no": "INTEGER",
        "old_name": "TEXT",
        "new_name": "TEXT",
        "year": "INTEGER",
        "office": "TEXT",
    }, rows)

def chain_query(from_wanted_name: bool) -> str:
    """
    The intended solution, built from the same CHAIN the data was built from so
    the check cannot drift from the puzzle. With `from_wanted_name` false it is
    the structural question instead -- whose chain runs through all ten years,
    whoever they started as -- which is the query that accuses two people.
    """
    joins = [f"JOIN name_changes c{step} ON c{step}.old_name = c{step - 1}.new_name"
             f" AND c{step}.year = {year}"
             for step, (year, _) in enumerate(CHAIN[1:], start=2)]
    where = f"c1.year = {CHAIN[0][0]}"
    if from_wanted_name:
        where = f"c1.old_name = '{WANTED_NAME}' AND {where}"
    return (f"SELECT c{len(CHAIN)}.new_name FROM name_changes c1\n"
            + "\n".join(joins) + f"\nWHERE {where}")

def walk(connection: sqlite3.Connection) -> List[str]:
    """
    The same chain walked one query at a time, the way a player without a
    ten-way join would do it. Raises unless every step has exactly one answer.
    """
    name = WANTED_NAME
    walked = []
    for year, expected in CHAIN:
        rows = connection.execute(
            "SELECT new_name FROM name_changes WHERE old_name = ? AND year = ?",
            (name, year)).fetchall()
        require(len(rows) == 1,
                f"step {year} of the chain has {len(rows)} answers, not one")
        name = rows[0][0]
        require(name == expected,
                f"step {year} gave {name!r} rather than {expected!r}")
        walked.append(name)
    return walked

def names(connection: sqlite3.Connection, query: str,
          parameters: Sequence = ()) -> List[str]:
    "Runs a solution attempt and returns the names it accuses, in order."
    return sorted(row[0] for row in connection.execute(query, parameters))

def verify(connection: sqlite3.Connection) -> None:
    """
    Re-checks every property the case depends on, against the same constants
    the data was built from, and raises rather than leave an unsolvable case
    behind. Changing a count above and re-running is therefore safe.
    """
    # What the evidence claims about the calendar: ten years at large and a
    # change of name in every year since 2017 on the warrant, and the date the
    # call was logged on the transcript. The chain has to start where the
    # warrant stops and end in the year the call came in.
    require(CHAIN[0][0] == FLED_YEAR + 1,
            "the chain does not start the year after he fled, so the wanted"
            " file's 'every year since 2017' is wrong")
    require(CHAIN[-1][0] == TODAY.year == LOG_LAST_YEAR,
            "the chain does not reach the year the call came in")
    require(len(CHAIN) == TODAY.year - FLED_YEAR,
            f"the chain is {len(CHAIN)} names long, which is not the ten years"
            " the warrant says he has been at large")

    # The registry. One row per person, each under one name, and no two people
    # answering to the same one -- so the chain's last step names one resident.
    require(count(connection, "SELECT COUNT(*) FROM residents") == RESIDENT_COUNT,
            "the registry is not the size the artwork says")
    require(count(connection, "SELECT COUNT(DISTINCT name) FROM residents")
            == RESIDENT_COUNT, "two residents answer to the same name")
    require(count(connection, "SELECT COUNT(*) FROM residents WHERE "
                              "name NOT LIKE '% %' OR name LIKE '% % %'") == 0,
            "a resident's name is not two words, so the column is untidy")

    # The premise: a name somebody has given up exists only in the log. This is
    # what stops `WHERE name = 'Allison Burgers'` -- or any intermediate name --
    # answering the case in one line.
    require(
        count(connection, """
            SELECT COUNT(*) FROM residents WHERE name IN
                (SELECT old_name FROM name_changes)
        """) == 0,
        "a name somebody gave up is still in the registry",
    )
    for name in CULPRIT_NAMES[:-1]:
        require(count(connection, "SELECT COUNT(*) FROM residents WHERE name = ?",
                      (name,)) == 0,
                f"{name!r} can be looked up in the registry")
    require(count(connection, "SELECT COUNT(*) FROM residents WHERE name = ?",
                  (CULPRIT_NAME,)) == 1,
            "the chain's last name is not one living resident")

    # Everybody at the end of a chain is a resident, which is what lets the
    # chain-end shortcut return real people rather than ghosts.
    require(
        count(connection, """
            SELECT COUNT(*) FROM name_changes WHERE new_name NOT IN
                (SELECT old_name FROM name_changes)
              AND new_name NOT IN (SELECT name FROM residents)
        """) == 0,
        "somebody's last new name is not in the registry",
    )

    # The intended solution, both shapes of it, naming one man.
    require(names(connection, chain_query(True)) == [CULPRIT_NAME],
            "the ten-way self join does not name exactly the culprit")
    require(walk(connection)[-1] == CULPRIT_NAME,
            "walking the chain a year at a time does not reach the culprit")

    # Every trap, in the order a player meets them.
    wanted_rows = names(connection,
                        "SELECT new_name FROM name_changes WHERE old_name = ?",
                        (WANTED_NAME,))
    require(len(wanted_rows) == 2,
            f"the wanted name has {len(wanted_rows)} onward changes, not two")
    require(CHAIN[0][1] in wanted_rows, "the culprit's first change is missing")
    require(
        names(connection, "SELECT new_name FROM name_changes WHERE "
                          "old_name = ? AND year = ?",
              (WANTED_NAME, CHAIN[0][0])) == [CHAIN[0][1]],
        "the wanted name plus 2017 is not a single row",
    )
    require(
        count(connection, "SELECT COUNT(*) FROM name_changes WHERE new_name = ?",
              (WANTED_NAME,)) == 1,
        "the hoax that gave somebody else the wanted name is not in the log",
    )
    require(
        sorted(HOAXER["years"]) == list(HOAXER["years"])
        and all(later - earlier > 1
                for earlier, later in zip(HOAXER["years"], HOAXER["years"][1:])),
        "the hoaxer renamed himself in consecutive years, so the chain's own"
        " rule would not shake him off",
    )
    hoaxer_end = HOAXER["names"][-1]
    hoaxer_row = connection.execute(
        "SELECT district, occupation FROM residents WHERE name = ?",
        (hoaxer_end,)).fetchall()
    require(len(hoaxer_row) == 1,
            "the hoaxer's chain does not end at a living resident, so starting"
            " on his row would return nothing rather than accuse somebody")
    require(hoaxer_row[0] == (README_HOAXER_DISTRICT, README_HOAXER_OCCUPATION),
            f"the hoaxer is a {hoaxer_row[0][1].lower()} in {hoaxer_row[0][0]},"
            f" not a {README_HOAXER_OCCUPATION.lower()} in"
            f" {README_HOAXER_DISTRICT} as the README says")

    # The shared names on the chain. Each has two onward changes, only one of
    # them in the culprit's next year.
    for name in TWIN_NAMES:
        onward = count(connection,
                       "SELECT COUNT(*) FROM name_changes WHERE old_name = ?",
                       (name,))
        require(onward == 2, f"{name!r} has {onward} onward changes, not two")
    # ... and the sharpest of the three: his 2024 name also leaves in 2026.
    late = TWINS[-1]
    shared, decoy_end = late["names"][1], late["names"][-1]
    require(
        names(connection, "SELECT new_name FROM name_changes WHERE "
                          "old_name = ? AND year = ?",
              (shared, LOG_LAST_YEAR)) == [decoy_end],
        f"{shared!r} has no 2026 change, so assuming the last change must be"
        " stamped in 2026 would not accuse anybody",
    )
    require(decoy_end != CULPRIT_NAME, "the 2026 decoy is the culprit himself")

    # Asking the question structurally accuses two: him and the understudy.
    structural = names(connection, chain_query(False))
    require(structural == sorted([CULPRIT_NAME, UNDERSTUDY["names"][-1]]),
            f"the structural question accuses {structural}, not the culprit and"
            " the understudy")

    # The chain-end shortcut.
    ends = names(connection, """
        SELECT new_name FROM name_changes WHERE year = ?
          AND new_name NOT IN (SELECT old_name FROM name_changes)
    """, (LOG_LAST_YEAR,))
    require(len(ends) == END_2026_TOTAL,
            f"the chain-end shortcut accuses {len(ends)}, not {END_2026_TOTAL}")
    require(CULPRIT_NAME in ends, "the chain-end shortcut misses the culprit")

    # Picking the daft name out of the column by eye.
    daft = [name for name in names(connection, "SELECT name FROM residents")
            if is_sign_name(name)]
    require(len(daft) == SIGN_RESIDENT_TOTAL,
            f"{len(daft)} residents carry a sign name, not {SIGN_RESIDENT_TOTAL}")
    require(CULPRIT_NAME in daft, "the culprit's own name is not a sign name")

    # No number this script writes may reach the Int32 ceiling: the case does
    # not merely display one oddly, it refuses to load at all.
    for table, column in (("residents", "resident_no"),
                          ("name_changes", "change_no"),
                          ("name_changes", "year")):
        biggest = count(connection, f"SELECT MAX({column}) FROM {table}")
        require(biggest <= INT32_MAX,
                f"{table}.{column} reaches {biggest}, over the Int32 ceiling")

    # Stopping at 2025 leaves nine people called Max.
    maxes = names(connection,
                  f"SELECT name FROM residents WHERE name LIKE '{MAX_FIRST_NAME} %'")
    require(len(maxes) == MAX_RESIDENT_COUNT,
            f"{len(maxes)} residents are called {MAX_FIRST_NAME}, not"
            f" {MAX_RESIDENT_COUNT}")

    # The fad has to be visible in the log, or the culprit's chain is the only
    # daft thing in it and a player reads the answer off the column.
    logged = {row[0] for row in connection.execute(
        "SELECT old_name FROM name_changes UNION SELECT new_name FROM name_changes")}
    in_log = sorted(name for name in logged if is_sign_name(name))
    require(len(in_log) == README_SIGN_NAMES_IN_LOG,
            f"{len(in_log)} sign names appear in the log, not"
            f" {README_SIGN_NAMES_IN_LOG}")

    # The log itself: inside the registry's span, numbered in step with the
    # year, and nothing in the ordering that singles the culprit out.
    changes = count(connection, "SELECT COUNT(*) FROM name_changes")
    require(
        count(connection, "SELECT COUNT(*) FROM name_changes WHERE "
                          f"year < {LOG_FIRST_YEAR} OR year > {LOG_LAST_YEAR}") == 0,
        "a change is stamped outside the registry's log",
    )
    require(
        count(connection, """
            SELECT COUNT(*) FROM name_changes a JOIN name_changes b
              ON b.change_no > a.change_no WHERE b.year < a.year
        """) == 0,
        "the log's numbers do not climb with the year",
    )
    # His own ten rows, picked out by name *and* year: three of those names are
    # shared with a twin, so old_name alone would drag their rows in too.
    his_rows = " OR ".join("(old_name = ? AND year = ?)" for _ in CHAIN)
    his_parameters = [value for step, (year, _) in enumerate(CHAIN)
                      for value in (CULPRIT_NAMES[step], year)]
    require(
        count(connection, "SELECT COUNT(DISTINCT office) FROM name_changes "
                          f"WHERE {his_rows}", his_parameters)
        == README_CULPRIT_OFFICES,
        f"the culprit filed his changes at a number of counters other than"
        f" {README_CULPRIT_OFFICES}, which the README quotes",
    )
    require(count(connection, f"SELECT COUNT(*) FROM name_changes WHERE {his_rows}",
                  his_parameters) == len(CHAIN),
            "the culprit's chain is not exactly ten rows")
    first_change, last_change = connection.execute(
        "SELECT MIN(change_no), MAX(change_no) FROM name_changes").fetchone()
    culprit_numbers = [row[0] for row in connection.execute(
        f"SELECT change_no FROM name_changes WHERE {his_rows}", his_parameters)]
    require(first_change not in culprit_numbers
            and last_change not in culprit_numbers,
            "the culprit filed the first or the last change in the log")

    # Figures the README quotes and the draw rather than the construction
    # fixes, so a rebuild that moves one fails instead of making the README lie.
    resident_no = count(connection,
                        "SELECT resident_no FROM residents WHERE name = ?",
                        (CULPRIT_NAME,))
    require(resident_no == README_CULPRIT_RESIDENT_NO,
            f"the culprit's registry number is {resident_no}, not"
            f" {README_CULPRIT_RESIDENT_NO}")
    require(changes == README_CHANGE_ROWS,
            f"the log has {changes} rows, not {README_CHANGE_ROWS}")

    print(f"Wrote {DATABASE_PATH}")
    print(f"{RESIDENT_COUNT} residents and {changes} changes stamped between"
          f" {LOG_FIRST_YEAR} and {LOG_LAST_YEAR}")
    print(f"The chain runs {WANTED_NAME} -> {' -> '.join(walk(connection))}")
    print(f"He is resident {resident_no}, a {CULPRIT_OCCUPATION.lower()} in"
          f" {CULPRIT_DISTRICT}")
    print(f"The wanted name has {len(wanted_rows)} onward changes; the"
          f" structural question accuses {len(structural)}; the chain-end"
          f" shortcut accuses {len(ends)}")
    print(f"{len(daft)} residents carry a sign name and {len(in_log)} appear in"
          f" the log; {len(maxes)} residents are called {MAX_FIRST_NAME}")

def is_sign_name(name: str) -> bool:
    """
    Whether a name was copied off a sign. The pools are the only authority on
    that -- there is no column saying so, which is the point.
    """
    return name in SIGN_POOL or name in SIGN_NAME_INDEX

SIGN_NAME_INDEX = frozenset(
    [name for _, name in CHAIN if name != "Max Wellhouse"]
    + list(HOAXER["names"][2:])
    + list(UNDERSTUDY["names"][1:])
    + [twin["names"][-1] for twin in TWINS]
    + list(SIGN_RESIDENTS)
)

def count(connection: sqlite3.Connection, query: str, parameters: Sequence = ()):
    row = connection.execute(query, parameters).fetchone()
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
