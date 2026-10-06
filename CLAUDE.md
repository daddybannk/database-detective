# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A workspace for authoring **custom cases** for the game _Database Detective_ and publishing them to its Steam Workshop. It is not the game's source.

```
CLAUDE.md
dbd-workshop/        git submodule -> github.com/BoyNamedHsu/dbd-workshop (upstream's authoring kit)
Sources/             our generators and artwork sources, one folder per case
Where Are You/       a finished case folder, ready to copy into the game
One Dollar/          the same, for the second case
Top of the Class/    the same, for the third case
School Speed Limit/  the same, for the fourth case
```

A case is two folders with the same name: `Sources/<case>/` holds the generator, the `build.sh` and the `.svg` sources; `<case>/` at the top level holds only what ships — `config.json`, the database, the PNGs and a `README.md` recording the solution. Both build steps in `Sources/<case>/` write across into `<case>/`.

**`dbd-workshop/` is a submodule and stays pristine.** It is upstream's kit — the format documentation (`README.md`, `Example Case/README.md`), the `Example Case/` reference case, PSD art templates, and the shared Python helpers in `Scripts/`. Read it, import from it, never write into it: anything added there is untracked by both repos and is destroyed the next time the submodule is re-cloned. Our code reaches across the boundary instead (see `Sources/Where Are You/where.py`, which puts `dbd-workshop/Scripts` on `sys.path` to import `db_utils`).

The unit of work is a **case folder**: a `config.json` plus a SQLite database file and media assets, all siblings in one directory. The game loads that folder; nothing is compiled or packaged.

## Commands

No build, test, or lint setup and no dependencies — Python standard library only, plus `rsvg-convert` (`brew install librsvg`) for artwork. Run from the repository root:

```bash
git submodule update --init         # a fresh clone leaves dbd-workshop/ empty,
                                    # and where.py imports db_utils from inside it

python3 "Sources/Where Are You/where.py"   # rebuild the case database, straight into "Where Are You/"
"Sources/Where Are You/build.sh"           # re-render the SVG artwork, straight into "Where Are You/"

python3 "Sources/One Dollar/one_dollar.py" # the same pair for the second case
"Sources/One Dollar/build.sh"

python3 "Sources/Top of the Class/top_of_the_class.py" # and for the third
"Sources/Top of the Class/build.sh"

python3 "Sources/School Speed Limit/school_speed_limit.py" # and for the fourth
"Sources/School Speed Limit/build.sh"

python3 dbd-workshop/Scripts/halloween.py  # upstream's example generator; writes into the cwd
```

To test a case, copy its folder into the game's data directory (`~/Library/Application Support/com.HsuCorp.copOS` on macOS; see `dbd-workshop/README.md` for Windows/Linux), then use the in-game _Custom Crimes Division_ → _Custom Cases_ panel to Load and Upload. Updating an already-published case means editing the files under `Steam/steamapps/workshop/content/3950130`, not the original folder.

## Case folder contract

`dbd-workshop/Example Case/README.md` documents every `config.json` field. The constraints that are easy to get wrong:

- Every path in `config.json` is a **bare filename resolved against the case folder** — no subdirectories. This is why `Sources/` is kept out of the case folder: only shippable files belong there.
- The `database` value is the database file's exact name, which has no extension (`where_are_you`, `halloween`).
- Transcripts work two different ways. A transcript for an entry in `evidenceAudioFiles` must be a `.txt` file with the **same basename as the audio file**; `voiceMessageTranscript` is an explicit filename. The example case therefore carries two byte-identical copies of the same text.
- Evidence images: max 1000x1000, max 8 entries. `previewImage` and `arrestWarrant` are **not** bound by that limit — the example case ships them at 2188x2188 and 2550x2188.
- `queryHints` and `caseHints` do not wrap. Insert literal `\n` to break lines, around 35 characters each.
- `lockedTables` should list every table the puzzle needs; otherwise players can drop them.
- **The in-game SQL console has no `CASE` expression.** A case has to be solvable with `WHERE`, `AND` and `OR` alone, so a banded comparison is written out one band per branch — see `mismatch_condition()` in `Sources/Top of the Class/top_of_the_class.py`, which builds that string from the scale so `verify()` tests the query a player actually types.

## How the database generators work

`dbd-workshop/Scripts/db_utils.py` is the shared layer:
- `@database_connection(path)` wraps a function so it receives an open `sqlite3.Connection` as a **keyword** argument named `connection`, inside a `with` block.
- `create_populate_table(connection, table_name, columns, rows)` takes `columns` as an ordered `{name: sql_type}` mapping; that mapping drives both the DDL and the column order of the parameterized inserts, and `rows` are dicts keyed by those same names.
- `get_random_name()` samples the word lists in `dbd-workshop/Scripts/Names/`.

The important thing to understand before editing a generator is that **the puzzle's difficulty is encoded in the data distribution, not in any rule engine.** In `Sources/Where Are You/where.py`:

- Five houses match the witness photograph exactly and only one of them is unpaid, so the description alone cannot name the culprit; 32 houses are unpaid, so the ledger alone cannot either. The case needs both halves.
- Every clue is load bearing: `DECOY_HOUSES` gives each of the six clues an unpaid house matching the other five, so dropping any clue returns more than one suspect. `31347` specifically punishes `LIKE '3%13%'`.
- Random houses are kept off the `3%13` pattern by `matches_plate()`, which is what makes the five description matches exact.
- Rows are sorted by house number before insert so the culprit is not conspicuously first.

`Sources/One Dollar/one_dollar.py` does the same job with aggregates instead of filters, and shows two more things worth copying:

- **Money is whole dollars in an `INTEGER` column, and no case should use fractions.** The game does not render decimals, and `REAL` columns would hand the puzzle to floating point error: measured on this data stored as dollars-and-cents, the intended `basket - paid = 0.01` matched *nobody*, and `basket > paid` accused 32 members who had paid exactly right. `ROUND(..., 2)` rescues the first query but not the second.
- The three traps are the same idea as the other case's decoys, aimed at aggregation instead: repeat purchases are separate rows so `SUM(DISTINCT price)` silently undercounts the culprit out of the result; 25 members have no rows in either `purchases` or `payments`; and 18 overpayers — one of them by exactly a dollar — mean `<>` returns 19 rows and `ABS(...) = 1` returns 2.

Note that the story has to match the data: the registers are $76 **over** overall, because the overpayers more than cover the missing dollar, which is why the evidence is a per-member exception report and not a till reconciliation. Check any figure quoted on evidence artwork against the database before shipping it.

`Sources/Top of the Class/top_of_the_class.py` is the smallest of the four: one forged grade among 450, found by testing each recorded grade against the band its exam score belongs in. Its single trap is the band boundary — twelve scores sit exactly on 80, 70, 60 and 50 and are graded correctly, so `>` instead of `>=` accuses thirteen students, and a `CASE` that forgets the D band accuses 51. `honest_score()` keeps the random scores off those four cut-offs, which is what fixes that count at twelve and lets the evidence artwork quote it.

`Sources/School Speed Limit/school_speed_limit.py` is the one case with a trap pointing each way, which is the whole of its difficulty: eight vehicles pass at exactly the 40 km/h zone limit so `speed >= 40` accuses nine drivers, while the culprit crosses the camera at `1500` — the restricted window's own edge — so `time > 1500` accuses nobody at all. A player has to be strict about the speed and inclusive about the time in the same `WHERE` clause. Two more counts punish getting the windows wrong: merging `600-800` and `1500-1700` into one span accuses 18, and rounding the edges outwards accuses 6.

Two things in it are worth copying into any case that stores a time:

- **Times are HHMM in an `INTEGER` column** (`1500` is 15:00, `801` is 08:01), and `random_time()` rejects any draw whose minute half reaches 60, because `760` is not a clock time. `verify()` asserts the same thing against the finished table. Minutes-from-midnight would also work, but HHMM is what a player reads off the evidence without converting.
- **`compliant_speed()` keeps every random pass below the limit**, so each wrong query's suspect count is fixed by construction rather than by the draw, and `verify()` can assert the exact number instead of just "more than one". The one count that falls out of the seeded draw instead — passes inside the windows — is pinned to a constant anyway, so a rebuild that moves it fails rather than quietly making the artwork lie.

Three habits in these generators worth keeping in any new one:

- `one_dollar.py` seeds its RNG from a constant, so a rebuild reproduces the shipped database byte for byte. Without that, every rebuild invalidates whatever figures the artwork and README quote. `where.py` does not seed, so its docs only quote values that are fixed by construction.
- `verify()` runs at the end of generation and raises unless all of the above still holds. It checks against the same clue list the data is built from, so the checks cannot drift from the puzzle. Changing any count or colour and re-running is therefore safe — the script refuses to leave an unsolvable case behind.
- `main()` unlinks the database file first. `CREATE TABLE IF NOT EXISTS` plus `INSERT` means a second run against an existing file silently appends duplicate rows; upstream's `halloween.py` still has that trap.

Each case folder's own `README.md` carries the intended solution query and the invariants that keep it the only answer — read `Where Are You/README.md` before changing that case's data, rather than re-deriving the puzzle from the generator.

## Python version gotcha

Upstream's `halloween.py` annotates with `sqlite3.Connection` and `typing.Tuple` but imports neither. It only runs because Python 3.14 evaluates annotations lazily (PEP 649); on 3.13 or earlier it raises `NameError` at import. `where.py` has the imports and does not have this problem.

Authoring a new case means copying a generator and changing the constants and table builders — expect near-duplicate scripts side by side rather than a shared framework.
