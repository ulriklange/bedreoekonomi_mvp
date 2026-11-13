"""Import one bank CSV export into Lakebase.

Run from the repository root with --preview first. The --apply option safely
adds new rows and skips rows already seen in earlier exports.
"""

import argparse
import csv
import hashlib
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.database import ensure_schema, get_connection
from app.schemas import BankCategory, TransactionCreate, main_category_for


REQUIRED_COLUMNS = {
    "Dato",
    "Tekst",
    "Beløb",
    "Saldo",
    "Kontonummer",
    "Hovedkategori",
    "Kategori",
}


@dataclass
class BankCsvTransaction:
    transaction: TransactionCreate
    main_category: str
    fingerprint: str
    match_key: tuple[date, str, Decimal]


def parse_amount(value: str) -> Decimal:
    """Parse Danish amounts such as -9.900,04 or 245,50."""
    normalized = value.strip().replace(".", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation as error:
        raise ValueError("Beløb kunne ikke læses som et dansk tal") from error


def read_transactions(csv_path: Path) -> list[BankCsvTransaction]:
    transactions: list[BankCsvTransaction] = []
    row_errors: list[str] = []
    duplicate_occurrences: dict[str, int] = defaultdict(int)

    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file, delimiter=";")
        if reader.fieldnames is None:
            raise ValueError("CSV-filen mangler kolonneoverskrifter")

        missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing_columns:
            raise ValueError(
                "CSV-filen mangler kolonner: " + ", ".join(sorted(missing_columns))
            )

        for row_number, row in enumerate(reader, start=2):
            try:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("rækken har et forkert antal felter")

                category = BankCategory(row["Kategori"].strip())
                transaction_date = datetime.strptime(
                    row["Dato"].strip(), "%d.%m.%Y"
                ).date()
                merchant = row["Tekst"].strip()
                amount = parse_amount(row["Beløb"])
                transaction = TransactionCreate(
                    merchant=merchant,
                    amount=amount,
                    date=transaction_date,
                    category=category,
                )

                expected_parent = main_category_for(category.value)
                supplied_parent = row.get("Hovedkategori", "").strip()
                if supplied_parent and supplied_parent != expected_parent:
                    raise ValueError("Hovedkategori passer ikke til Kategori")

                account_number = "".join(row["Kontonummer"].split())
                balance = parse_amount(row["Saldo"])
                identity = {
                    "account": account_number,
                    "date": transaction_date.isoformat(),
                    "merchant": merchant,
                    "amount": format(amount.normalize(), "f"),
                    "balance": format(balance.normalize(), "f"),
                }
                identity_json = json.dumps(
                    identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                duplicate_occurrences[identity_json] += 1
                fingerprint = hashlib.sha256(
                    f"{identity_json}:{duplicate_occurrences[identity_json]}".encode(
                        "utf-8"
                    )
                ).hexdigest()

                transactions.append(
                    BankCsvTransaction(
                        transaction=transaction,
                        main_category=supplied_parent or expected_parent,
                        fingerprint=fingerprint,
                        match_key=(
                            transaction_date,
                            merchant,
                            amount,
                        ),
                    )
                )
            except (ValueError, KeyError, InvalidOperation) as error:
                row_errors.append(f"Række {row_number}: {error}")

    if row_errors:
        details = "\n".join(row_errors[:20])
        if len(row_errors) > 20:
            details += f"\n... og {len(row_errors) - 20} flere fejl"
        raise ValueError(f"CSV-importen stoppede på grund af ugyldige rækker:\n{details}")
    if not transactions:
        raise ValueError("CSV-filen indeholder ingen posteringer")
    return transactions


def import_transactions(
    transactions: list[BankCsvTransaction],
) -> tuple[int, int, int, list[str]]:
    inserted_count = 0
    backfilled_count = 0
    skipped_count = 0
    category_changes: list[str] = []

    with get_connection() as connection:
        ensure_schema(connection)
        existing_rows = connection.execute(
            """
            SELECT id, merchant, amount, transaction_date, main_category,
                   category, source_fingerprint
            FROM transactions
            ORDER BY id
            """
        ).fetchall()
        known_fingerprints = {
            row[6]: (row[0], row[4], row[5])
            for row in existing_rows
            if row[6] is not None
        }
        unkeyed_rows: dict[
            tuple[date, str, Decimal], deque[tuple[int, str, str]]
        ] = defaultdict(deque)
        for row in existing_rows:
            if row[6] is None:
                unkeyed_rows[(row[3], row[1], row[2])].append(
                    (row[0], row[4], row[5])
                )

        with connection.cursor() as cursor:
            for item in transactions:
                if item.fingerprint in known_fingerprints:
                    transaction_id, old_main_category, old_category = (
                        known_fingerprints[item.fingerprint]
                    )
                    if (
                        old_main_category != item.main_category
                        or old_category != item.transaction.category.value
                    ):
                        cursor.execute(
                            "UPDATE transactions SET main_category = %s, category = %s "
                            "WHERE id = %s",
                            (
                                item.main_category,
                                item.transaction.category.value,
                                transaction_id,
                            ),
                        )
                        category_changes.append(
                            f"{item.transaction.date.isoformat()} "
                            f"{item.transaction.merchant}: "
                            f"{old_main_category} / {old_category} → "
                            f"{item.main_category} / {item.transaction.category.value}"
                        )
                        known_fingerprints[item.fingerprint] = (
                            transaction_id,
                            item.main_category,
                            item.transaction.category.value,
                        )
                    else:
                        skipped_count += 1
                    continue

                matching_ids = unkeyed_rows.get(item.match_key)
                if matching_ids:
                    legacy_id, old_main_category, old_category = matching_ids.popleft()
                    updated = cursor.execute(
                        "UPDATE transactions SET source_fingerprint = %s, "
                        "main_category = %s, category = %s "
                        "WHERE id = %s AND source_fingerprint IS NULL",
                        (
                            item.fingerprint,
                            item.main_category,
                            item.transaction.category.value,
                            legacy_id,
                        ),
                    )
                    if updated.rowcount:
                        known_fingerprints[item.fingerprint] = (
                            legacy_id,
                            item.main_category,
                            item.transaction.category.value,
                        )
                        backfilled_count += 1
                        if (
                            old_main_category != item.main_category
                            or old_category != item.transaction.category.value
                        ):
                            category_changes.append(
                                f"{item.transaction.date.isoformat()} "
                                f"{item.transaction.merchant}: "
                                f"{old_main_category} / {old_category} → "
                                f"{item.main_category} / {item.transaction.category.value}"
                            )
                    else:
                        skipped_count += 1
                    continue

                inserted = cursor.execute(
                    """
                    INSERT INTO transactions
                        (merchant, amount, transaction_date, main_category,
                         category, source_fingerprint)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_fingerprint) DO NOTHING
                    RETURNING id
                    """,
                    (
                        item.transaction.merchant,
                        item.transaction.amount,
                        item.transaction.date,
                        item.main_category,
                        item.transaction.category.value,
                        item.fingerprint,
                    ),
                ).fetchone()
                if inserted is None:
                    skipped_count += 1
                else:
                    inserted_count += 1
                    known_fingerprints[item.fingerprint] = (
                        inserted[0],
                        item.main_category,
                        item.transaction.category.value,
                    )

    return inserted_count, backfilled_count, skipped_count, category_changes


def main() -> None:
    parser = argparse.ArgumentParser(description="Importer bankens CSV til Lakebase")
    parser.add_argument("csv_file", type=Path, help="Sti til CSV-filen")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preview", action="store_true", help="Kontrollér filen uden at gemme")
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Synkronisér nye posteringer og spring dubletter over",
    )
    args = parser.parse_args()

    transactions = read_transactions(args.csv_file)
    print(f"CSV-filen er læst: {len(transactions)} gyldige posteringer.")

    if args.preview:
        print("Forhåndsvisning færdig. Ingen data blev gemt.")
        return

    inserted, backfilled, skipped, category_changes = import_transactions(transactions)
    print(
        "Synkronisering færdig: "
        f"{inserted} nye posteringer, "
        f"{backfilled} eksisterende posteringer fik dubletnøgle, "
        f"{len(category_changes)} kategorier opdateret fra banken, "
        f"{skipped} dubletter sprunget over."
    )
    for change in category_changes:
        print(f"  Kategori ændret: {change}")


if __name__ == "__main__":
    main()
