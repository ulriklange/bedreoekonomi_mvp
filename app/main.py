from contextlib import asynccontextmanager
from datetime import date as Date
from decimal import Decimal
import os
from pathlib import Path

import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from psycopg.conninfo import make_conninfo
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / "user.env"
if not ENV_FILE.exists():
    ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(ENV_FILE)

required_settings = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
missing_settings = [name for name in required_settings if not os.getenv(name)]
if missing_settings:
    raise RuntimeError(
        f"Missing database settings in {ENV_FILE.name}: {', '.join(missing_settings)}"
    )

DB_CONNECTION = make_conninfo(
    host=os.environ["DB_HOST"],
    port=5432,
    dbname=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    sslmode=os.getenv("DB_SSLMODE", "require"),
)


class TransactionCreate(BaseModel):
    merchant: str = Field(min_length=1, examples=["Netto"])
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2, examples=[245.50])
    date: Date = Field(examples=["2026-11-11"])
    category: str = Field(min_length=1, examples=["Mad"])


class Transaction(TransactionCreate):
    id: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    with psycopg.connect(DB_CONNECTION) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id BIGSERIAL PRIMARY KEY,
                merchant TEXT NOT NULL,
                amount NUMERIC(10, 2) NOT NULL CHECK (amount > 0),
                transaction_date DATE NOT NULL,
                category TEXT NOT NULL
            )
            """
        )
    yield


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
    with psycopg.connect(DB_CONNECTION) as connection:
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
    with psycopg.connect(DB_CONNECTION) as connection:
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
    with psycopg.connect(DB_CONNECTION) as connection:
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
    with psycopg.connect(DB_CONNECTION) as connection:
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
    with psycopg.connect(DB_CONNECTION) as connection:
        row = connection.execute(
            "DELETE FROM transactions WHERE id = %s RETURNING id",
            (transaction_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
