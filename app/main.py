from fastapi import FastAPI, HTTPException
from .database import lifespan
from .schemas import Transaction, TransactionCreate
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


@app.post("/transactions", response_model=Transaction, tags=["transactions"])
def create_transaction(transaction: TransactionCreate) -> Transaction:
    return transactions_repository.create_transaction(transaction)


@app.get("/transactions", response_model=list[Transaction], tags=["transactions"])
def list_transactions() -> list[Transaction]:
    return transactions_repository.list_transactions()


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
