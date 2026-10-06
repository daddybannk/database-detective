"""
Generates the SQLite database for the custom case "One Dollar".

The supermarket's audit found one member who paid a dollar less than their
basket came to. Every item that crossed the scanner is one row in `purchases`,
so a member who took two of the same thing has that product twice; what each
member handed over is one row in `payments`. The answer is the member whose
basket totals one dollar more than they paid.

Prices are whole dollars stored as INTEGER. The game does not render decimals,
and SQLite would decide a fractional comparison by floating point error anyway
(2.49 + 1.99 is 4.4799999999999995), so there are no fractions anywhere.

As in `where.py`, the difficulty lives in the data distribution rather than in
any rule engine, and three traps sit between the player and the answer:
  * repeat purchases -- SUM(DISTINCT price) silently undercounts the culprit
    and drops them out of the result;
  * members who never shopped -- no rows in `purchases` and none in
    `payments`, so a careless LEFT JOIN has to cope with NULL;
  * overpayers -- 18 members handed over too much, one of them by exactly a
    dollar, so `<>` and `ABS(...) = 1` both return more than one suspect.

`verify()` asserts all of the above and runs automatically, so the script
refuses to leave an unsolvable database behind.

Run from anywhere:  python3 "Sources/One Dollar/one_dollar.py"
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

DATABASE_NAME = "supermarket"
DATABASE_PATH = REPO / "One Dollar" / DATABASE_NAME # written straight into the case folder

SEED = 20260206 # fixed, so a rebuild reproduces the shipped case exactly --
                # the evidence artwork and README quote figures from this data
CULPRIT_NAME = "Buck Mulgrew"
MEMBER_COUNT = 220
NON_SHOPPER_COUNT = 25 # members with no basket and no payment at all
OVERPAYER_COUNT = 18 # members who handed over too much, decoys for every one of them
SHORTFALL = 1 # dollars the culprit held back, and what the audit is missing
OVERPAY_MIN = 2 # rounding up to the next note, so never more than a few dollars
OVERPAY_MAX = 9

BASKET_MIN = 3
BASKET_MAX = 12
REPEAT_SHOPPER_RATE = 0.4 # how many shoppers take more than one of something

# name, price in whole dollars
PRODUCTS = [
    ("Whole Milk 1L", 2), ("Skim Milk 1L", 2), ("Butter 250g", 4),
    ("Cheddar Block", 7), ("Greek Yoghurt", 3), ("Free Range Eggs x12", 5),
    ("Sourdough Loaf", 4), ("White Bread", 2), ("Bagels x6", 3),
    ("Bananas 1kg", 2), ("Red Apples 1kg", 3), ("Navel Oranges 1kg", 4),
    ("Strawberries", 5), ("Blueberries", 6), ("Avocado", 2),
    ("Roma Tomatoes 500g", 3), ("Baby Spinach", 3), ("Carrots 1kg", 2),
    ("Brown Onions 1kg", 2), ("Potatoes 2kg", 4), ("Broccoli", 3),
    ("Chicken Breast 500g", 9), ("Beef Mince 500g", 10), ("Pork Chops", 8),
    ("Streaky Bacon", 6), ("Salmon Fillet", 13), ("Tinned Tuna", 2),
    ("Spaghetti 500g", 2), ("Penne 500g", 2), ("Basmati Rice 1kg", 5),
    ("Rolled Oats 1kg", 3), ("Corn Flakes", 4), ("Peanut Butter", 5),
    ("Strawberry Jam", 3), ("Clover Honey", 8), ("Olive Oil 500ml", 11),
    ("Sea Salt", 2), ("Black Pepper", 3), ("Ground Coffee 250g", 9),
    ("Tea Bags x80", 4), ("Orange Juice 1L", 4), ("Sparkling Water x6", 5),
    ("Dark Chocolate", 3), ("Potato Crisps", 3), ("Vanilla Ice Cream", 6),
    ("Dish Soap", 4), ("Paper Towels x4", 5), ("Toothpaste", 4),
]

@database_connection(str(DATABASE_PATH))
def create_tables(connection: sqlite3.Connection) -> None:
    product_rows = build_products()
    member_rows, purchase_rows, payment_rows = build_baskets(product_rows)
    create_members_table(connection, member_rows)
    create_products_table(connection, product_rows)
    create_purchases_table(connection, purchase_rows)
    create_payments_table(connection, payment_rows)
    verify(connection)

def build_products() -> list:
    "One row per item the shop sells."
    return [
        {"product_id": index, "name": name, "price": price}
        for index, (name, price) in enumerate(PRODUCTS, start=1)
    ]

def build_baskets(product_rows: list) -> Tuple[list, list, list]:
    """
    Builds the member, purchase and payment rows together, because what someone
    paid only makes sense next to what they carried out.
    Returns a tuple of (members, purchases, payments).
    """
    member_rows = []
    purchase_rows = []
    payment_rows = []

    culprit_id = random.randint(2, MEMBER_COUNT - 1) # never first, never last
    shopper_ids = pick_shoppers(culprit_id)
    overpayer_ids = pick_overpayers(shopper_ids, culprit_id)
    dollar_overpayer_id = overpayer_ids[0] # the decoy that defeats ABS(...) = 1

    taken_names = {CULPRIT_NAME}
    for member_id in range(1, MEMBER_COUNT + 1):
        is_culprit = member_id == culprit_id
        member_rows.append({
            "member_id": member_id,
            "name": CULPRIT_NAME if is_culprit else next_name(taken_names),
        })
        if member_id not in shopper_ids:
            continue # never came in, so no basket and nothing to pay

        basket = build_basket(product_rows, force_repeat=is_culprit)
        for product in basket:
            purchase_rows.append({
                "member_id": member_id,
                "product_id": product["product_id"],
            })

        total = sum(product["price"] for product in basket)
        payment_rows.append({
            "member_id": member_id,
            "paid": settle(member_id, total, culprit_id, overpayer_ids, dollar_overpayer_id),
        })

    return member_rows, purchase_rows, payment_rows

def settle(member_id: int, total: int, culprit_id: int, overpayer_ids: list, dollar_overpayer_id: int) -> int:
    "What the member actually handed over."
    if member_id == culprit_id:
        return total - SHORTFALL
    if member_id == dollar_overpayer_id:
        # Short by one and over by one have to look alike, or ABS() solves it.
        return total + SHORTFALL
    if member_id in overpayer_ids:
        return total + random.randint(OVERPAY_MIN, OVERPAY_MAX)
    return total

def pick_shoppers(culprit_id: int) -> set:
    "Everyone except the members who never came in. The culprit always shops."
    everyone = set(range(1, MEMBER_COUNT + 1)) - {culprit_id}
    stayed_home = set(random.sample(sorted(everyone), NON_SHOPPER_COUNT))
    return (everyone - stayed_home) | {culprit_id}

def pick_overpayers(shopper_ids: set, culprit_id: int) -> list:
    "Members who handed over too much. Never the culprit."
    candidates = sorted(shopper_ids - {culprit_id})
    return random.sample(candidates, OVERPAYER_COUNT)

def build_basket(product_rows: list, force_repeat: bool) -> list:
    "A basket, where taking two of something means the product appears twice."
    distinct = random.sample(product_rows, random.randint(BASKET_MIN, BASKET_MAX))
    basket = list(distinct)
    if force_repeat or random.random() < REPEAT_SHOPPER_RATE:
        for _ in range(random.randint(1, 3)):
            basket.append(random.choice(distinct))
    random.shuffle(basket)
    return basket

def next_name(taken: set) -> str:
    "A unique member name, so the arrest is never ambiguous."
    while True:
        first_name, last_name = get_random_name()
        name = f"{first_name} {last_name}"
        if name not in taken:
            taken.add(name)
            return name

def create_members_table(connection: sqlite3.Connection, member_rows: list) -> None:
    create_populate_table(connection, "members", {
        "member_id": "INTEGER",
        "name": "TEXT",
    }, member_rows)

def create_products_table(connection: sqlite3.Connection, product_rows: list) -> None:
    create_populate_table(connection, "products", {
        "product_id": "INTEGER",
        "name": "TEXT",
        "price": "INTEGER",
    }, product_rows)

def create_purchases_table(connection: sqlite3.Connection, purchase_rows: list) -> None:
    create_populate_table(connection, "purchases", {
        "member_id": "INTEGER",
        "product_id": "INTEGER",
    }, purchase_rows)

def create_payments_table(connection: sqlite3.Connection, payment_rows: list) -> None:
    create_populate_table(connection, "payments", {
        "member_id": "INTEGER",
        "paid": "INTEGER",
    }, payment_rows)

BASKET_TOTALS = """
    SELECT m.name AS name,
           SUM(p.price) AS basket,
           pa.paid AS paid
    FROM members m
    JOIN purchases pu ON pu.member_id = m.member_id
    JOIN products  p  ON p.product_id = pu.product_id
    JOIN payments  pa ON pa.member_id = m.member_id
    GROUP BY m.member_id, m.name
"""

DISTINCT_TOTALS = BASKET_TOTALS.replace("SUM(p.price)", "SUM(DISTINCT p.price)")

def names_where(connection: sqlite3.Connection, totals: str, condition: str) -> list:
    "Runs a solution attempt and returns the members it accuses."
    query = f"SELECT name FROM ({totals}) WHERE {condition} ORDER BY name"
    return [row[0] for row in connection.execute(query)]

def verify(connection: sqlite3.Connection) -> None:
    "Fails loudly rather than leaving an unsolvable case behind."
    solution = names_where(connection, BASKET_TOTALS, f"basket - paid = {SHORTFALL}")
    require(
        solution == [CULPRIT_NAME],
        f"the intended solution should name only {CULPRIT_NAME}, got {solution}",
    )

    mismatched = names_where(connection, BASKET_TOTALS, "basket <> paid")
    require(
        len(mismatched) > 1,
        f"`basket <> paid` should leave several suspects, got {mismatched}",
    )

    off_by_one = names_where(connection, BASKET_TOTALS, f"ABS(basket - paid) = {SHORTFALL}")
    require(
        len(off_by_one) > 1,
        f"`ABS(basket - paid) = 1` should leave several suspects, got {off_by_one}",
    )

    deduped = names_where(connection, DISTINCT_TOTALS, f"basket - paid = {SHORTFALL}")
    require(
        CULPRIT_NAME not in deduped,
        "SUM(DISTINCT price) still finds the culprit, so repeat purchases are not a trap",
    )

    require(
        count(connection, f"""
            SELECT COUNT(*) FROM purchases pu
            JOIN members m ON m.member_id = pu.member_id
            WHERE m.name = '{CULPRIT_NAME}'
            GROUP BY pu.product_id HAVING COUNT(*) > 1 LIMIT 1
        """) is not None,
        "the culprit bought nothing twice, so SUM(DISTINCT ...) would still work on them",
    )

    underpaid = names_where(connection, BASKET_TOTALS, "basket > paid")
    require(
        underpaid == [CULPRIT_NAME],
        f"exactly one member should have underpaid, got {underpaid}",
    )

    idle = count(connection, """
        SELECT COUNT(*) FROM members
        WHERE member_id NOT IN (SELECT member_id FROM purchases)
    """)
    require(idle == NON_SHOPPER_COUNT, f"expected {NON_SHOPPER_COUNT} members with no basket, got {idle}")
    require(
        count(connection, """
            SELECT COUNT(*) FROM members
            WHERE member_id NOT IN (SELECT member_id FROM purchases)
              AND member_id IN (SELECT member_id FROM payments)
        """) == 0,
        "a member with no basket still has a payment row",
    )

    require(
        count(connection, "SELECT COUNT(DISTINCT name) FROM members") == MEMBER_COUNT,
        "member names are not unique",
    )
    require(
        count(connection, "SELECT COUNT(*) FROM payments") == MEMBER_COUNT - NON_SHOPPER_COUNT,
        "shoppers and payment rows do not line up",
    )
    require(
        count(connection, "SELECT COUNT(*) FROM products WHERE price <> CAST(price AS INTEGER)") == 0,
        "a price is not a whole number of dollars",
    )

    print(f"Wrote {DATABASE_PATH}")
    print(f"Culprit: {CULPRIT_NAME}, short by ${SHORTFALL}")
    print(f"{MEMBER_COUNT} members, {idle} of them never shopped")
    print(f"{len(mismatched)} members paid something other than their basket total")
    print(f"{len(off_by_one)} of those are a dollar out, in one direction or the other")
    print("Repeat purchases, idle members and overpayers are all live traps.")

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
