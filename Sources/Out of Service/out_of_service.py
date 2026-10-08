"""
Generates the SQLite database for the custom case "Out of Service".

The night the bank's ATM network lost its link to the ledger, every machine
fell back on the balance it had last synced before the crash. Each withdrawal
was still checked -- against that stale figure, one transaction at a time --
so nothing the machines dispensed that night was ever added up. One customer
worked out what that meant and kept going until they had taken more cash than
their account held.

A machine holds three cassettes, so a withdrawal is recorded the way the
machine counts it out: one column per note, `n1000`, `n500` and `n100`. What
somebody actually took is `n1000*1000 + n500*500 + n100*100`, which makes every
amount a whole number of dollars and keeps the case clear of the fractions that
`one_dollar.py` records the cost of.

The difficulty lives in the data distribution rather than in any rule engine,
and here every tempting shortcut points somewhere else:

  * no single withdrawal exceeds the balance it was checked against, so
    comparing one row at a time accuses nobody -- the overdraw only exists as a
    total, which is what forces GROUP BY;
  * seven accounts were emptied to exactly zero, so `>=` accuses eight;
  * the culprit is only $270 over, which is less than the hundreds they
    took and less than the five hundreds, so a query that forgets either
    cassette accuses nobody;
  * counting notes instead of valuing them accuses nobody either, and the
    account holding the night's biggest pile of notes is innocent;
  * three accounts withdrew more cash than the culprit and one filed more
    transactions, so sorting by either ranking arrests the wrong customer;
  * nine accounts were never touched that night, so a `LEFT JOIN` has to cope
    with NULL.

Ordinary accounts are kept at least $100 inside their balance by
`build_withdrawals()`, which is what makes all of those counts exact by
construction rather than by luck, the same way `compliant_speed()` pins them in
`school_speed_limit.py`.

Times are whole numbers, written the way the machine prints them: 2015 is
20:15, and 1960 is not a time at all.

`verify()` asserts all of the above and runs automatically, so the script
refuses to leave an unsolvable database behind.

Run from anywhere:  python3 "Sources/Out of Service/out_of_service.py"
"""
import random
import sqlite3
import sys
from pathlib import Path
from typing import List, Tuple

# db_utils and its name lists come from the upstream workshop kit, which is
# vendored as a submodule and deliberately left untouched -- so reach into it
# rather than copying it out.
REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "dbd-workshop" / "Scripts"))

from db_utils import create_populate_table, database_connection, get_random_name

DATABASE_NAME = "atm_network"
DATABASE_PATH = REPO / "Out of Service" / DATABASE_NAME # straight into the case folder

SEED = 20261014 # fixed, so a rebuild reproduces the shipped case exactly --
                # the evidence artwork and README quote figures from this data
CULPRIT_NAME = "Edric Pennal" # pinned by name, the way the other cases pin theirs

ACCOUNT_COUNT = 60

# The numbers the bank prints on things, and how wide each one is. They carry
# no information -- an account number says nothing about its balance and a
# reference number says nothing about the amount -- so a player sorting by
# either learns nothing from them.
# Eight digits for a reference number, not twelve: the game reads an INTEGER
# column into a signed 32-bit int, so anything past INT32_MAX fails to load
# with "Value was either too large or too small for an Int32". Twelve-digit
# reference numbers ran to 988,168,933,048, which no console could open. Eight
# is the widest that stays clear of the ceiling and still cannot be mistaken
# for a six-digit account number.
ACCOUNT_ID_DIGITS = 6
MACHINE_ID_DIGITS = 4
WITHDRAWAL_ID_DIGITS = 8
INT32_MAX = 2147483647

# The three cassettes every machine on the network is loaded with, and the most
# it will count out in one transaction. Both are printed on the evidence, and
# verify() checks the database against them.
NOTE_VALUES = (1000, 500, 100)
NOTE_COLUMNS = ("n1000", "n500", "n100")
TRANSACTION_CAP = 4000
AMOUNT_STEP = min(NOTE_VALUES) # so every amount in the log is a whole number of
                               # hundreds, with no note smaller than a hundred

# The machines kept dispensing from 19:41, when the link dropped, until the
# ledger came back at midnight. Times are HHMM.
OUTAGE_START = 1941
OUTAGE_END = 2359

MACHINES = (
    "Lindenhall Branch, lobby",
    "Lindenhall Branch, drive-up",
    "Fenn Street kiosk",
    "Market Square",
    "Quarry Road garage",
)

BALANCE_MIN = 1500
BALANCE_MAX = 48000
ROUND_BALANCE_RATE = 0.3 # ordinary accounts whose balance also lands on a round
                         # hundred, so the seven emptied accounts below are not
                         # the only round figures in the table

# Everyone ordinary. Capped at three transactions and kept a hundred dollars clear
# of their balance, which is what fixes every suspect count below by
# construction instead of by the draw.
ORDINARY_ROWS = (1, 3)
ORDINARY_HUNDREDS = (0, 6)
ORDINARY_MARGIN = AMOUNT_STEP

NO_WITHDRAWAL_COUNT = 9 # accounts with no rows in withdrawals at all
EXACT_ZERO_COUNT = 7    # emptied to exactly zero: total withdrawn = balance
EXACT_ZERO_ROWS = (2, 4)
EXACT_ZERO_HUNDREDS = (20, 110) # the balance, in hundreds, before the split

# The culprit's night, pinned rather than drawn: five transactions, none of them
# larger than the balance they were checked against, $270 over in total.
CULPRIT_BALANCE = 12730
CULPRIT_WITHDRAWALS = (
    (4, 0, 0), # 4000
    (3, 0, 2), # 3200
    (2, 1, 0), # 2500
    (1, 1, 3), # 1800
    (1, 1, 0), # 1500
)

# The account that walked away with the night's biggest pile of notes -- 47 of
# them, all hundreds -- and was well inside its balance the whole time.
NOTE_PILE_BALANCE = 9850
NOTE_PILE_WITHDRAWALS = ((0, 0, 20), (0, 0, 15), (0, 0, 12))

# The account that used a machine more often than anybody else, the culprit
# included, so `ORDER BY COUNT(*)` arrests the wrong customer.
FREQUENT_BALANCE = 31500
FREQUENT_WITHDRAWALS = ((1, 0, 0),) * 6 + ((4, 0, 0),)

# Five accounts that took more cash than the culprit and had it to take, so
# `ORDER BY SUM(...)` arrests the wrong customer too.
HEAVY_SPENDERS = (
    (46800, ((4, 0, 0), (4, 0, 0), (4, 0, 0), (4, 0, 0))),          # 16000
    (38200, ((4, 0, 0), (4, 0, 0), (3, 1, 0), (3, 0, 8))),          # 15300
    (24600, ((4, 0, 0), (3, 1, 0), (3, 0, 2), (2, 1, 5))),          # 13700
    (29400, ((4, 0, 0), (4, 0, 0), (3, 1, 0), (2, 0, 5))),          # 14000
    (19800, ((4, 0, 0), (4, 0, 0), (3, 0, 6), (2, 1, 0))),          # 14100
)

def cash(notes: Tuple[int, int, int]) -> int:
    "What a transaction came to, the way the solution query values it."
    return sum(count * value for count, value in zip(notes, NOTE_VALUES))

CULPRIT_TOTAL = sum(cash(notes) for notes in CULPRIT_WITHDRAWALS)
CULPRIT_OVERDRAW = CULPRIT_TOTAL - CULPRIT_BALANCE
CULPRIT_NOTES = sum(sum(notes) for notes in CULPRIT_WITHDRAWALS)

# Figures printed on the evidence artwork. verify() checks them against the
# database, so a rebuild that changes the data fails instead of quietly making
# the artwork lie.
ARTWORK_NOTE_VALUES = NOTE_VALUES
ARTWORK_OUTAGE = (OUTAGE_START, OUTAGE_END)
# Quoted in the case README only -- the card no longer prints the cap, but the
# data still has to honour it or the README lies.
README_CAP = TRANSACTION_CAP
# Not fixed by construction the way the counts are -- it falls out of the seeded
# draw, which is exactly why verify() pins it.
ARTWORK_WITHDRAWALS_LOGGED = 131

# Figures quoted in the case README, each one a wrong query's answer, all fixed
# by construction. verify() proves every one of them.
README_AT_OR_OVER_SUSPECTS = EXACT_ZERO_COUNT + 1 # SUM(...) >= balance
README_EMPTIED_ACCOUNTS = EXACT_ZERO_COUNT
README_NO_WITHDRAWAL_ACCOUNTS = NO_WITHDRAWAL_COUNT
README_BIGGER_SPENDERS = len(HEAVY_SPENDERS)
README_NOTE_PILE = sum(sum(notes) for notes in NOTE_PILE_WITHDRAWALS)
README_FREQUENT_ROWS = len(FREQUENT_WITHDRAWALS)
README_CULPRIT_ROWS = len(CULPRIT_WITHDRAWALS)
# Falls out of the seeded draw rather than the construction, so verify() pins it.
README_MORE_NOTES = 5

@database_connection(str(DATABASE_PATH))
def create_tables(connection: sqlite3.Connection) -> None:
    account_rows, plan = build_accounts()
    machine_rows = build_machines()
    withdrawal_rows = build_withdrawals(account_rows, plan, machine_rows)
    create_accounts_table(connection, account_rows)
    create_machines_table(connection, machine_rows)
    create_withdrawals_table(connection, withdrawal_rows)
    verify(connection)

def build_accounts() -> Tuple[List[dict], dict]:
    """
    Every account on the network, and which part each one plays in the night.
    The culprit sits somewhere in the middle of the list rather than at either
    end. Returns (accounts, {account_id: pinned withdrawals or None}).
    """
    culprit_id = random.randint(2, ACCOUNT_COUNT - 1) # never first, never last
    others = [account_id for account_id in range(1, ACCOUNT_COUNT + 1)
              if account_id != culprit_id]
    pinned_count = 2 + len(HEAVY_SPENDERS)
    marked = random.sample(others, NO_WITHDRAWAL_COUNT + EXACT_ZERO_COUNT + pinned_count)

    at = 0
    def take(count: int) -> list:
        nonlocal at
        at += count
        return marked[at - count:at]

    no_withdrawal = set(take(NO_WITHDRAWAL_COUNT))
    emptied = set(take(EXACT_ZERO_COUNT))
    note_pile, = take(1)
    frequent, = take(1)
    heavy = take(len(HEAVY_SPENDERS))

    balances = {culprit_id: CULPRIT_BALANCE, note_pile: NOTE_PILE_BALANCE,
                frequent: FREQUENT_BALANCE}
    plan = {culprit_id: CULPRIT_WITHDRAWALS, note_pile: NOTE_PILE_WITHDRAWALS,
            frequent: FREQUENT_WITHDRAWALS}
    for account_id, (balance, withdrawals) in zip(heavy, HEAVY_SPENDERS):
        balances[account_id] = balance
        plan[account_id] = withdrawals
    for account_id in emptied:
        balance, withdrawals = emptied_account()
        balances[account_id] = balance
        plan[account_id] = withdrawals
    for account_id in no_withdrawal:
        plan[account_id] = ()

    # The account numbers themselves, drawn last so the parts above stay keyed
    # by position while they are being handed out.
    numbers = unique_ids(ACCOUNT_COUNT, ACCOUNT_ID_DIGITS)
    taken_names = {CULPRIT_NAME}
    account_rows = [
        {
            "account_id": numbers[position - 1],
            "name": CULPRIT_NAME if position == culprit_id else next_name(taken_names),
            "balance": balances.get(position) or ordinary_balance(),
        }
        for position in range(1, ACCOUNT_COUNT + 1)
    ]
    return account_rows, {numbers[position - 1]: withdrawals
                          for position, withdrawals in plan.items()}

def unique_ids(count: int, digits: int) -> List[int]:
    "`count` distinct numbers of exactly `digits` digits, in ascending order."
    return sorted(random.sample(range(10 ** (digits - 1), 10 ** digits), count))

def ordinary_balance() -> int:
    """
    What an ordinary account held when the link dropped. Most of them do not
    land on a round hundred, but enough of them do that the accounts emptied to
    exactly zero are not conspicuous.
    """
    if random.random() < ROUND_BALANCE_RATE:
        return random.randrange(BALANCE_MIN, BALANCE_MAX, AMOUNT_STEP)
    while True:
        balance = random.randrange(BALANCE_MIN, BALANCE_MAX, 10)
        if balance % AMOUNT_STEP:
            return balance

def emptied_account() -> Tuple[int, tuple]:
    """
    An account taken down to exactly zero across two to four transactions. The
    total equals the balance, which is what makes `>=` accuse eight customers
    and `>` accuse one.
    """
    rows = random.randint(*EXACT_ZERO_ROWS)
    cap = TRANSACTION_CAP // AMOUNT_STEP
    while True:
        hundreds = random.randint(*EXACT_ZERO_HUNDREDS)
        if hundreds > rows * cap:
            continue
        split = random_split(hundreds, rows, cap)
        if split:
            return hundreds * AMOUNT_STEP, tuple(compose(part * AMOUNT_STEP) for part in split)

def random_split(total: int, parts: int, cap: int) -> list:
    "Splits `total` into `parts` whole amounts, each between 1 and `cap`, or []."
    for _ in range(200):
        split = [random.randint(1, cap) for _ in range(parts - 1)]
        last = total - sum(split)
        if 1 <= last <= cap:
            return split + [last]
    return []

def compose(amount: int) -> Tuple[int, int, int]:
    "Counts `amount` out of the three cassettes, largest note first."
    counts = []
    for value in NOTE_VALUES:
        counts.append(amount // value)
        amount %= value
    require(amount == 0, f"{amount} cannot be counted out of {NOTE_VALUES}")
    return tuple(counts)

def build_machines() -> List[dict]:
    "The machines on the network, every one of them dispensing blind that night."
    return [
        {"machine_id": machine_id, "location": location}
        for machine_id, location in zip(
            unique_ids(len(MACHINES), MACHINE_ID_DIGITS), MACHINES
        )
    ]

def build_withdrawals(account_rows: List[dict], plan: dict,
                      machine_rows: List[dict]) -> List[dict]:
    """
    Every transaction the machines logged during the outage. The pinned accounts
    carry the traps; everybody else took a few hundred or a few thousand and
    stayed at least a hundred dollars inside the balance the machines were checking
    against, which is what keeps the overdraw unique to the culprit.
    """
    machine_ids = [row["machine_id"] for row in machine_rows]
    rows = []
    for account in account_rows:
        withdrawals = plan.get(account["account_id"])
        if withdrawals is None:
            withdrawals = ordinary_withdrawals(account["balance"])
        for notes in withdrawals:
            require(
                cash(notes) <= account["balance"],
                f"a single transaction of {cash(notes)} exceeds the balance it was"
                f" checked against ({account['balance']}), so one row gives the answer",
            )
            rows.append({
                "account_id": account["account_id"],
                "machine_id": random.choice(machine_ids),
                "time": random_time(),
                "n1000": notes[0],
                "n500": notes[1],
                "n100": notes[2],
            })
    spread_culprit_times(rows, culprit_id(account_rows))

    # Sorted by the time on the transaction, so the culprit's are not
    # conspicuously first in the table.
    rows.sort(key=lambda row: (row["time"], row["account_id"]))
    for withdrawal_id, row in zip(unique_ids(len(rows), WITHDRAWAL_ID_DIGITS), rows):
        row["withdrawal_id"] = withdrawal_id
    return rows

def ordinary_withdrawals(balance: int) -> list:
    """
    One to three transactions that leave the account in credit with room to
    spare. The allowance is what pins the suspect counts: nobody ordinary can
    drift up to their balance, let alone past it.
    """
    allowance = balance - ORDINARY_MARGIN
    withdrawals = []
    for _ in range(random.randint(*ORDINARY_ROWS)):
        cap = min(TRANSACTION_CAP, allowance)
        if cap < min(NOTE_VALUES):
            break
        notes = ordinary_transaction(cap)
        withdrawals.append(notes)
        allowance -= cash(notes)
    return withdrawals

def ordinary_transaction(cap: int) -> Tuple[int, int, int]:
    "What a customer asked a machine for: a few notes, never more than `cap`."
    while True:
        hundreds = random.randint(*ORDINARY_HUNDREDS)
        rest = cap - hundreds * AMOUNT_STEP
        if rest < 0:
            continue
        thousands = random.randint(0, rest // 1000)
        rest -= thousands * 1000
        five_hundreds = random.randint(0, min(1, rest // 500))
        notes = (thousands, five_hundreds, hundreds)
        if cash(notes) >= min(NOTE_VALUES):
            return notes

def random_time() -> int:
    """
    A time the machine could have printed. Times are HHMM, so the minute half
    has to stay under 60 -- 2359 is a real time and 1960 is not.
    """
    while True:
        time = random.randint(OUTAGE_START, OUTAGE_END)
        if time % 100 < 60:
            return time

def spread_culprit_times(rows: List[dict], account_id: int) -> None:
    """
    Redraws the culprit's times until theirs is neither the first nor the last
    transaction of the night. Without this the draw could hand the answer to
    anybody who sorts the log by time.
    """
    culprit_rows = [row for row in rows if row["account_id"] == account_id]
    others = [row["time"] for row in rows if row["account_id"] != account_id]
    first, last = min(others), max(others)
    while True:
        times = [row["time"] for row in culprit_rows]
        if min(times) > first and max(times) < last:
            return
        for row in culprit_rows:
            row["time"] = random_time()

def culprit_id(account_rows: List[dict]) -> int:
    return next(row["account_id"] for row in account_rows if row["name"] == CULPRIT_NAME)

def next_name(taken: set) -> str:
    "A unique account holder, so the arrest is never ambiguous."
    while True:
        first_name, last_name = get_random_name()
        name = f"{first_name} {last_name}"
        if name not in taken:
            taken.add(name)
            return name

def create_accounts_table(connection: sqlite3.Connection, account_rows: List[dict]) -> None:
    create_populate_table(connection, "accounts", {
        "account_id": "INTEGER",
        "name": "TEXT",
        "balance": "INTEGER",
    }, account_rows)

def create_machines_table(connection: sqlite3.Connection, machine_rows: List[dict]) -> None:
    create_populate_table(connection, "machines", {
        "machine_id": "INTEGER",
        "location": "TEXT",
    }, machine_rows)

def create_withdrawals_table(connection: sqlite3.Connection, rows: List[dict]) -> None:
    create_populate_table(connection, "withdrawals", {
        "withdrawal_id": "INTEGER",
        "account_id": "INTEGER",
        "machine_id": "INTEGER",
        "time": "INTEGER",
        "n1000": "INTEGER",
        "n500": "INTEGER",
        "n100": "INTEGER",
    }, rows)

LEDGER = """
    SELECT a.account_id AS account_id,
           a.name       AS name,
           a.balance    AS balance,
           w.time       AS time,
           w.n1000      AS n1000,
           w.n500       AS n500,
           w.n100       AS n100
    FROM accounts a
    JOIN withdrawals w ON w.account_id = a.account_id
"""

CASH = "n1000*1000 + n500*500 + n100*100"
WITHOUT_HUNDREDS = "n1000*1000 + n500*500"
WITHOUT_FIVE_HUNDREDS = "n1000*1000 + n100*100"
NOTE_COUNT = "n1000 + n500 + n100"

def names_having(connection: sqlite3.Connection, having: str) -> List[str]:
    "Runs a solution attempt and returns the account holders it accuses."
    query = f"""
        SELECT name FROM ({LEDGER})
        GROUP BY account_id, name, balance
        HAVING {having}
        ORDER BY name
    """
    return [row[0] for row in connection.execute(query)]

def ranking(connection: sqlite3.Connection, expression: str, limit: int = 5) -> List[str]:
    "The account holders a shortcut puts at the top of its ranking."
    query = f"""
        SELECT name FROM ({LEDGER})
        GROUP BY account_id, name, balance
        ORDER BY {expression} DESC, name
        LIMIT {limit}
    """
    return [row[0] for row in connection.execute(query)]

def verify(connection: sqlite3.Connection) -> None:
    "Fails loudly rather than leaving an unsolvable case behind."
    accused = names_having(connection, f"SUM({CASH}) > balance")
    require(
        accused == [CULPRIT_NAME],
        f"the intended solution should name only {CULPRIT_NAME}, got {accused}",
    )

    at_or_over = names_having(connection, f"SUM({CASH}) >= balance")
    require(
        len(at_or_over) == README_AT_OR_OVER_SUSPECTS and CULPRIT_NAME in at_or_over,
        f"`SUM(...) >= balance` should accuse {README_AT_OR_OVER_SUSPECTS} customers"
        f" including the culprit, got {at_or_over}",
    )

    per_row = [row[0] for row in connection.execute(f"""
        SELECT DISTINCT name FROM ({LEDGER}) WHERE {CASH} > balance
    """)]
    require(
        per_row == [],
        f"a single transaction already exceeds its balance, so GROUP BY is not"
        f" needed: {per_row}",
    )

    for name, expression in (
        ("the hundreds", WITHOUT_HUNDREDS),
        ("the five hundreds", WITHOUT_FIVE_HUNDREDS),
        ("the note values", NOTE_COUNT),
    ):
        dropped = names_having(connection, f"SUM({expression}) > balance")
        require(
            dropped == [],
            f"forgetting {name} should accuse nobody, got {dropped}",
        )

    by_notes = ranking(connection, f"SUM({NOTE_COUNT})", limit=3)
    require(
        CULPRIT_NAME not in by_notes,
        f"the culprit is in the top {len(by_notes)} by notes taken, so counting"
        " notes points at them by accident",
    )
    more_notes = count(connection, f"""
        SELECT COUNT(*) FROM (
            SELECT account_id FROM ({LEDGER}) GROUP BY account_id
            HAVING SUM({NOTE_COUNT}) > {CULPRIT_NOTES}
        )
    """)
    require(
        more_notes == README_MORE_NOTES,
        f"the README quotes {README_MORE_NOTES} customers who took more notes than"
        f" the culprit, found {more_notes}",
    )
    pile = count(connection, f"""
        SELECT MAX(notes) FROM (
            SELECT SUM({NOTE_COUNT}) AS notes FROM ({LEDGER}) GROUP BY account_id
        )
    """)
    require(
        pile == README_NOTE_PILE,
        f"the README quotes {README_NOTE_PILE} notes as the night's biggest pile,"
        f" found {pile}",
    )

    by_cash = ranking(connection, f"SUM({CASH})", limit=len(HEAVY_SPENDERS))
    require(
        CULPRIT_NAME not in by_cash,
        f"the culprit is in the top {len(by_cash)} by cash taken, so sorting by"
        " the total points at them without comparing it to anything",
    )
    bigger = count(connection, f"""
        SELECT COUNT(*) FROM (
            SELECT account_id FROM ({LEDGER}) GROUP BY account_id
            HAVING SUM({CASH}) > {CULPRIT_TOTAL}
        )
    """)
    require(
        bigger == README_BIGGER_SPENDERS,
        f"the README quotes {README_BIGGER_SPENDERS} customers who took more cash"
        f" than the culprit, found {bigger}",
    )

    by_rows = ranking(connection, "COUNT(*)", limit=1)
    require(
        CULPRIT_NAME not in by_rows,
        "the culprit filed the most transactions, so sorting by COUNT(*) names"
        " them for free",
    )
    busiest = count(connection, """
        SELECT MAX(rows) FROM (
            SELECT COUNT(*) AS rows FROM withdrawals GROUP BY account_id
        )
    """)
    require(
        busiest == README_FREQUENT_ROWS,
        f"the README quotes {README_FREQUENT_ROWS} transactions as the night's"
        f" busiest account, found {busiest}",
    )

    biggest = count(connection, f"SELECT MAX({CASH}) FROM withdrawals")
    sharing = count(connection, f"""
        SELECT COUNT(*) FROM (
            SELECT account_id FROM withdrawals WHERE {CASH} = {biggest}
            GROUP BY account_id
        )
    """)
    require(
        biggest == README_CAP and sharing > 1,
        f"the largest single transaction should be the machine's {README_CAP} cap"
        f" and shared by several accounts, got {biggest} across {sharing}",
    )

    culprit = connection.execute(f"""
        SELECT SUM({CASH}), COUNT(*), balance FROM ({LEDGER})
        WHERE name = '{CULPRIT_NAME}'
    """).fetchone()
    require(
        culprit == (CULPRIT_TOTAL, README_CULPRIT_ROWS, CULPRIT_BALANCE),
        f"the culprit should take {CULPRIT_TOTAL} across {README_CULPRIT_ROWS}"
        f" transactions against {CULPRIT_BALANCE}, got {culprit}",
    )
    culprit_hundreds = count(connection, f"""
        SELECT SUM(n100*100) FROM ({LEDGER}) WHERE name = '{CULPRIT_NAME}'
    """)
    culprit_five_hundreds = count(connection, f"""
        SELECT SUM(n500*500) FROM ({LEDGER}) WHERE name = '{CULPRIT_NAME}'
    """)
    require(
        CULPRIT_OVERDRAW > 0
        and CULPRIT_OVERDRAW < culprit_hundreds
        and CULPRIT_OVERDRAW < culprit_five_hundreds,
        f"the overdraw of {CULPRIT_OVERDRAW} is not smaller than both the culprit's"
        f" hundreds ({culprit_hundreds}) and their five hundreds"
        f" ({culprit_five_hundreds}), so forgetting a cassette would still find them",
    )

    emptied = count(connection, f"""
        SELECT COUNT(*) FROM (
            SELECT account_id FROM ({LEDGER}) GROUP BY account_id, balance
            HAVING SUM({CASH}) = balance
        )
    """)
    require(
        emptied == README_EMPTIED_ACCOUNTS,
        f"the README quotes {README_EMPTIED_ACCOUNTS} accounts emptied to exactly"
        f" zero, found {emptied}",
    )
    round_balances = count(
        connection, f"SELECT COUNT(*) FROM accounts WHERE balance % {AMOUNT_STEP} = 0"
    )
    require(
        round_balances > 2 * EXACT_ZERO_COUNT,
        f"only {round_balances} balances land on a round hundred, which makes the"
        f" {EXACT_ZERO_COUNT} emptied accounts conspicuous",
    )

    untouched = count(connection, """
        SELECT COUNT(*) FROM accounts a
        LEFT JOIN withdrawals w ON w.account_id = a.account_id
        WHERE w.withdrawal_id IS NULL
    """)
    require(
        untouched == README_NO_WITHDRAWAL_ACCOUNTS,
        f"the README quotes {README_NO_WITHDRAWAL_ACCOUNTS} accounts never touched"
        f" that night, found {untouched}",
    )

    first, last = connection.execute(
        "SELECT MIN(time), MAX(time) FROM withdrawals"
    ).fetchone()
    culprit_times = [row[0] for row in connection.execute(f"""
        SELECT time FROM ({LEDGER}) WHERE name = '{CULPRIT_NAME}' ORDER BY time
    """)]
    require(
        culprit_times[0] > first and culprit_times[-1] < last,
        "the culprit holds the first or the last transaction of the night, which"
        " points at them without adding anything up",
    )

    logged = count(connection, "SELECT COUNT(*) FROM withdrawals")
    require(
        logged == ARTWORK_WITHDRAWALS_LOGGED,
        f"the artwork quotes {ARTWORK_WITHDRAWALS_LOGGED} transactions logged,"
        f" found {logged}",
    )
    require(
        count(connection, f"""
            SELECT COUNT(*) FROM withdrawals
            WHERE {CASH} > {README_CAP} OR {CASH} < {min(NOTE_VALUES)}
              OR ({CASH}) % {AMOUNT_STEP} <> 0 -- the brackets matter: % binds
              OR n1000 < 0 OR n500 < 0 OR n100 < 0 -- tighter than + in SQLite
        """) == 0,
        f"a transaction breaks the machine's {README_CAP} cap or is not a whole"
        f" number of {AMOUNT_STEP}s",
    )
    require(
        count(connection, f"""
            SELECT COUNT(*) FROM withdrawals
            WHERE time % 100 >= 60 OR time < {ARTWORK_OUTAGE[0]}
              OR time > {ARTWORK_OUTAGE[1]}
        """) == 0,
        "a logged time is not a real clock time inside the outage the notice"
        " prints",
    )
    require(
        count(connection, """
            SELECT COUNT(*) FROM accounts
            WHERE balance <= 0 OR balance <> CAST(balance AS INTEGER)
        """) == 0,
        "an account's balance is not a whole positive number",
    )
    require(
        count(connection, """
            SELECT COUNT(*) FROM withdrawals w
            LEFT JOIN accounts a ON a.account_id = w.account_id
            WHERE a.name IS NULL
        """) == 0,
        "a transaction belongs to no account",
    )
    require(
        count(connection, """
            SELECT COUNT(*) FROM withdrawals w
            LEFT JOIN machines m ON m.machine_id = w.machine_id
            WHERE m.location IS NULL
        """) == 0,
        "a transaction came from a machine that is not on the network",
    )
    require(
        count(connection, "SELECT COUNT(DISTINCT name) FROM accounts") == ACCOUNT_COUNT,
        "account holder names are not unique",
    )
    for table, column, digits, rows in (
        ("accounts", "account_id", ACCOUNT_ID_DIGITS, ACCOUNT_COUNT),
        ("machines", "machine_id", MACHINE_ID_DIGITS, len(MACHINES)),
        ("withdrawals", "withdrawal_id", WITHDRAWAL_ID_DIGITS, logged),
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
        # The game loads an INTEGER column into an Int32, so an id past the
        # ceiling is not a cosmetic problem -- the case refuses to open.
        require(
            count(connection, f"SELECT COUNT(*) FROM {table} "
                              f"WHERE {column} > {INT32_MAX}") == 0,
            f"a {table}.{column} is larger than Int32 can hold, "
            f"which stops the game loading the case",
        )

    print(f"Wrote {DATABASE_PATH}")
    print(f"Culprit: {CULPRIT_NAME}, {CULPRIT_TOTAL} taken across"
          f" {README_CULPRIT_ROWS} transactions against a balance of"
          f" {CULPRIT_BALANCE} -- {CULPRIT_OVERDRAW} over")
    print(f"{ACCOUNT_COUNT} accounts, {logged} transactions logged,"
          f" {untouched} accounts never touched")
    print(f"`SUM(...) >= balance` accuses {len(at_or_over)}; {emptied} accounts were"
          " emptied to exactly zero")
    print("Comparing one transaction at a time accuses nobody, and so does"
          " forgetting either cassette or counting notes")
    print(f"{bigger} customers took more cash than the culprit; the busiest account"
          f" filed {busiest} transactions and the biggest pile was {pile} notes")

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
