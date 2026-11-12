from fastapi import FastAPI, HTTPException, Query
from .database import lifespan
from .schemas import (
    BankCategory,
    Transaction,
    TransactionCreate,
    TransactionSummary,
    category_hierarchy,
)
from . import transactions_repository


app = FastAPI(
    title="Bedre Økonomi API",
    description="API til Bedre Økonomi MVP.",
    version="0.3.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/categories", response_model=list[str], tags=["categories"])
def list_categories() -> list[str]:
    return [category.value for category in BankCategory]


@app.get(
    "/category-hierarchy",
    response_model=dict[str, list[str]],
    tags=["categories"],
)
def get_category_hierarchy() -> dict[str, list[str]]:
    return category_hierarchy()


@app.post("/transactions", response_model=Transaction, tags=["transactions"])
def create_transaction(transaction: TransactionCreate) -> Transaction:
    return transactions_repository.create_transaction(transaction)


@app.get("/transactions", response_model=list[Transaction], tags=["transactions"])
def list_transactions(
    category: BankCategory | None = Query(default=None),
) -> list[Transaction]:
    category_name = category.value if category is not None else None
    return transactions_repository.list_transactions(category_name)


@app.get(
    "/transactions/summary",
    response_model=TransactionSummary,
    tags=["transactions"],
)
def get_monthly_summary(
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
) -> TransactionSummary:
    return transactions_repository.summarize_month(year, month)


@app.get(
    "/transactions/{transaction_id}",
    response_model=Transaction,
    tags=["transactions"],
)
def get_transaction(transaction_id: int) -> Transaction:
    transaction = transactions_repository.get_transaction(transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@app.put(
    "/transactions/{transaction_id}",
    response_model=Transaction,
    tags=["transactions"],
)
def update_transaction(
    transaction_id: int,
    transaction: TransactionCreate,
) -> Transaction:
    updated_transaction = transactions_repository.update_transaction(
        transaction_id, transaction
    )
    if updated_transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return updated_transaction


@app.delete(
    "/transactions/{transaction_id}",
    status_code=204,
    tags=["transactions"],
)
def delete_transaction(transaction_id: int) -> None:
    deleted = transactions_repository.delete_transaction(transaction_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Transaction not found")
