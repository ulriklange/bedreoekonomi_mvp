from datetime import date

from .database import get_connection
from .schemas import CategoryTotal, Transaction, TransactionCreate, TransactionSummary


def _to_transaction(row) -> Transaction:
    return Transaction(
        id=row[0],
        merchant=row[1],
        amount=row[2],
        date=row[3],
        category=row[4],
    )


def create_transaction(transaction: TransactionCreate) -> Transaction:
    with get_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO transactions (merchant, amount, transaction_date, category)
            VALUES (%s, %s, %s, %s)
            RETURNING id, merchant, amount, transaction_date, category
            """,
            (
                transaction.merchant,
                transaction.amount,
                transaction.date,
                transaction.category.value,
            ),
        ).fetchone()

    return _to_transaction(row)


def list_transactions(category: str | None = None) -> list[Transaction]:
    query = """
        SELECT id, merchant, amount, transaction_date, category
        FROM transactions
    """
    parameters = ()

    if category is not None:
        query += " WHERE category = %s"
        parameters = (category,)

    query += " ORDER BY id"

    with get_connection() as connection:
        rows = connection.execute(query, parameters).fetchall()

    return [_to_transaction(row) for row in rows]


def summarize_month(year: int, month: int) -> TransactionSummary:
    start_date = date(year, month, 1)
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE transaction_date >= %s AND transaction_date < %s
            """,
            (start_date, next_month),
        ).fetchone()
        category_rows = connection.execute(
            """
            SELECT category, COUNT(*), SUM(amount)
            FROM transactions
            WHERE transaction_date >= %s AND transaction_date < %s
            GROUP BY category
            ORDER BY SUM(amount) DESC, category
            """,
            (start_date, next_month),
        ).fetchall()

    return TransactionSummary(
        year=year,
        month=month,
        transaction_count=row[0],
        total_amount=row[1],
        categories=[
            CategoryTotal(
                category=category_row[0],
                transaction_count=category_row[1],
                total_amount=category_row[2],
            )
            for category_row in category_rows
        ],
    )


def get_transaction(transaction_id: int) -> Transaction | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, merchant, amount, transaction_date, category
            FROM transactions
            WHERE id = %s
            """,
            (transaction_id,),
        ).fetchone()

    if row is None:
        return None
    return _to_transaction(row)


def update_transaction(
    transaction_id: int,
    transaction: TransactionCreate,
) -> Transaction | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            UPDATE transactions
            SET merchant = %s,
                amount = %s,
                transaction_date = %s,
                category = %s
            WHERE id = %s
            RETURNING id, merchant, amount, transaction_date, category
            """,
            (
                transaction.merchant,
                transaction.amount,
                transaction.date,
                transaction.category.value,
                transaction_id,
            ),
        ).fetchone()

    if row is None:
        return None
    return _to_transaction(row)


def delete_transaction(transaction_id: int) -> bool:
    with get_connection() as connection:
        row = connection.execute(
            "DELETE FROM transactions WHERE id = %s RETURNING id",
            (transaction_id,),
        ).fetchone()

    return row is not None
