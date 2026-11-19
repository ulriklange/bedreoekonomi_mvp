from calendar import monthrange
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .database import lifespan
from .schemas import (
    BankCategory,
    Transaction,
    TransactionCreate,
    TransactionHistory,
    TransactionSummary,
    MonthlyForecast,
    category_hierarchy,
)
from . import transactions_repository


WEB_DIR = Path(__file__).resolve().parent.parent / "web"


app = FastAPI(
    title="Bedre Økonomi API",
    description="API til Bedre Økonomi MVP.",
    version="0.3.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


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
    "/transactions/history",
    response_model=TransactionHistory,
    tags=["transactions"],
)
def get_transaction_history(
    from_date: date = Query(...),
    to_date: date = Query(...),
) -> TransactionHistory:
    if from_date > to_date:
        raise HTTPException(
            status_code=422,
            detail="from_date must be earlier than or equal to to_date",
        )
    return transactions_repository.get_monthly_history(from_date, to_date)


@app.get(
    "/forecast/monthly",
    response_model=MonthlyForecast,
    tags=["forecast"],
)
def get_monthly_forecast(
    forecast_year: int = Query(ge=2000, le=2100),
    forecast_month: int = Query(ge=1, le=12),
    history_from: date = Query(...),
    history_to: date = Query(...),
) -> MonthlyForecast:
    if history_from > history_to:
        raise HTTPException(
            status_code=422,
            detail="history_from must be earlier than or equal to history_to",
        )
    if history_from.day != 1 or history_to.day != monthrange(
        history_to.year, history_to.month
    )[1]:
        raise HTTPException(
            status_code=422,
            detail="Forecast history must contain complete calendar months",
        )

    months_used = (
        (history_to.year - history_from.year) * 12
        + history_to.month
        - history_from.month
        + 1
    )
    if months_used < 3:
        raise HTTPException(
            status_code=422,
            detail="At least three complete history months are required",
        )

    forecast_index = forecast_year * 12 + forecast_month
    history_end_index = history_to.year * 12 + history_to.month
    if forecast_index <= history_end_index:
        raise HTTPException(
            status_code=422,
            detail="Forecast month must be later than the history period",
        )

    return transactions_repository.forecast_monthly(
        forecast_year,
        forecast_month,
        history_from,
        history_to,
    )


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
