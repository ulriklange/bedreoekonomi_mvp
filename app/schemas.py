from datetime import date as Date
from decimal import Decimal

from pydantic import BaseModel, Field


class TransactionCreate(BaseModel):
    merchant: str = Field(min_length=1, examples=["Netto"])
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2, examples=[245.50])
    date: Date = Field(examples=["2026-11-11"])
    category: str = Field(min_length=1, examples=["Mad"])


class Transaction(TransactionCreate):
    id: int
