"""Import one bank CSV export into Lakebase.

Run from the repository root with --preview first. The --apply option only
imports when the transactions table is empty, to prevent accidental duplicates.
"""

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.database import get_connection
from app.schemas import BankCategory, TransactionCreate, main_category_for


REQUIRED_COLUMNS = {"Dato", "Tekst", "Beløb", "Kategori"}


@dataclass
class BankCsvTransaction:
    transaction: TransactionCreate
    main_category: str


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
                transaction = TransactionCreate(
                    merchant=row["Tekst"].strip(),
                    amount=parse_amount(row["Beløb"]),
                    date=datetime.strptime(row["Dato"].strip(), "%d.%m.%Y").date(),
                    category=category,
                )

                expected_parent = main_category_for(category.value)
                supplied_parent = row.get("Hovedkategori", "").strip()
                if supplied_parent and supplied_parent != expected_parent:
                    raise ValueError("Hovedkategori passer ikke til Kategori")

                transactions.append(
                    BankCsvTransaction(
                        transaction=transaction,
                        main_category=supplied_parent or expected_parent,
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


def import_transactions(transactions: list[BankCsvTransaction]) -> None:
    with get_connection() as connection:
        existing_count = connection.execute(
            "SELECT COUNT(*) FROM transactions"
        ).fetchone()[0]
        if existing_count:
            raise RuntimeError(
                "Tabellen indeholder allerede posteringer. Importen blev ikke kørt "
                "for at undgå dubletter."
            )

        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO transactions
                    (merchant, amount, transaction_date, main_category, category)
                VALUES (%s, %s, %s, %s, %s)
                """,
                [
                    (
                        item.transaction.merchant,
                        item.transaction.amount,
                        item.transaction.date,
                        item.main_category,
                        item.transaction.category.value,
                    )
                    for item in transactions
                ],
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Importer bankens CSV til Lakebase")
    parser.add_argument("csv_file", type=Path, help="Sti til CSV-filen")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preview", action="store_true", help="Kontrollér filen uden at gemme")
    mode.add_argument("--apply", action="store_true", help="Gem posteringerne i Lakebase")
    args = parser.parse_args()

    transactions = read_transactions(args.csv_file)
    print(f"CSV-filen er læst: {len(transactions)} gyldige posteringer.")

    if args.preview:
        print("Forhåndsvisning færdig. Ingen data blev gemt.")
        return

    import_transactions(transactions)
    print(f"Import færdig: {len(transactions)} posteringer gemt i Lakebase.")


if __name__ == "__main__":
    main()
