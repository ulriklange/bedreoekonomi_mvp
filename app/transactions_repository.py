from .database import get_connection
from .schemas import Transaction, TransactionCreate


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
                transaction.category,
            ),
        ).fetchone()

    return _to_transaction(row)


def list_transactions() -> list[Transaction]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, merchant, amount, transaction_date, category
            FROM transactions
            ORDER BY id
            """
        ).fetchall()

    return [_to_transaction(row) for row in rows]


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
                transaction.category,
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
