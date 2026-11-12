from fastapi import FastAPI, HTTPException
from .database import get_connection, lifespan
from .schemas import Transaction, TransactionCreate


app = FastAPI(
    title="Bedre Økonomi API",
    description="API til Bedre Økonomi MVP.",
    version="0.3.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/transactions", response_model=Transaction, tags=["transactions"])
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

    return Transaction(
        id=row[0], merchant=row[1], amount=row[2], date=row[3], category=row[4]
    )


@app.get("/transactions", response_model=list[Transaction], tags=["transactions"])
def list_transactions() -> list[Transaction]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, merchant, amount, transaction_date, category
            FROM transactions
            ORDER BY id
            """
        ).fetchall()

    return [
        Transaction(id=row[0], merchant=row[1], amount=row[2], date=row[3], category=row[4])
        for row in rows
    ]


@app.get(
    "/transactions/{transaction_id}",
    response_model=Transaction,
    tags=["transactions"],
)
def get_transaction(transaction_id: int) -> Transaction:
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
        raise HTTPException(status_code=404, detail="Transaction not found")

    return Transaction(
        id=row[0], merchant=row[1], amount=row[2], date=row[3], category=row[4]
    )


@app.put(
    "/transactions/{transaction_id}",
    response_model=Transaction,
    tags=["transactions"],
)
def update_transaction(
    transaction_id: int,
    transaction: TransactionCreate,
) -> Transaction:
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
        raise HTTPException(status_code=404, detail="Transaction not found")

    return Transaction(
        id=row[0], merchant=row[1], amount=row[2], date=row[3], category=row[4]
    )


@app.delete(
    "/transactions/{transaction_id}",
    status_code=204,
    tags=["transactions"],
)
def delete_transaction(transaction_id: int) -> None:
    with get_connection() as connection:
        row = connection.execute(
            "DELETE FROM transactions WHERE id = %s RETURNING id",
            (transaction_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
