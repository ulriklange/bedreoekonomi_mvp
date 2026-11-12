from datetime import date
from decimal import Decimal

from .database import get_connection
from .schemas import (
    CATEGORY_PARENTS,
    CategoryTotal,
    EXCLUDED_MAIN_CATEGORY,
    MainCategoryTotal,
    Transaction,
    TransactionCreate,
    TransactionSummary,
)


def _to_transaction(row) -> Transaction:
    return Transaction(
        id=row[0],
        merchant=row[1],
        amount=row[2],
        date=row[3],
        main_category=row[4],
        category=row[5],
    )


def create_transaction(transaction: TransactionCreate) -> Transaction:
    with get_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO transactions
                (merchant, amount, transaction_date, main_category, category)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, merchant, amount, transaction_date, main_category, category
            """,
            (
                transaction.merchant,
                transaction.amount,
                transaction.date,
                CATEGORY_PARENTS[transaction.category],
                transaction.category.value,
            ),
        ).fetchone()

    return _to_transaction(row)


def list_transactions(category: str | None = None) -> list[Transaction]:
    query = """
        SELECT id, merchant, amount, transaction_date, main_category, category
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
            SELECT COUNT(*),
                   COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0),
                   COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0),
                   COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE transaction_date >= %s AND transaction_date < %s
              AND main_category <> %s
            """,
            (start_date, next_month, EXCLUDED_MAIN_CATEGORY),
        ).fetchone()
        category_rows = connection.execute(
            """
            SELECT main_category,
                   category,
                   COUNT(*),
                   COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0),
                   COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0),
                   COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE transaction_date >= %s AND transaction_date < %s
            GROUP BY main_category, category
            ORDER BY SUM(ABS(amount)) DESC, main_category, category
            """,
            (start_date, next_month),
        ).fetchall()

    categories = [
        CategoryTotal(
            main_category=category_row[0],
            category=category_row[1],
            transaction_count=category_row[2],
            expense_total=category_row[3],
            income_total=category_row[4],
            net_total=category_row[5],
        )
        for category_row in category_rows
    ]
    parent_totals: dict[str, dict] = {}
    for category in categories:
        totals = parent_totals.setdefault(
            category.main_category,
            {
                "transaction_count": 0,
                "expense_total": Decimal("0"),
                "income_total": Decimal("0"),
                "net_total": Decimal("0"),
                "subcategories": [],
            },
        )
        totals["transaction_count"] += category.transaction_count
        totals["expense_total"] += category.expense_total
        totals["income_total"] += category.income_total
        totals["net_total"] += category.net_total
        totals["subcategories"].append(category)

    excluded_from_budget = parent_totals.pop(EXCLUDED_MAIN_CATEGORY, None)
    if excluded_from_budget is not None:
        excluded_from_budget = MainCategoryTotal(
            main_category=EXCLUDED_MAIN_CATEGORY,
            **excluded_from_budget,
        )

    main_categories = [
        MainCategoryTotal(main_category=name, **totals)
        for name, totals in sorted(
            parent_totals.items(),
            key=lambda item: item[1]["expense_total"] + item[1]["income_total"],
            reverse=True,
        )
    ]

    return TransactionSummary(
        year=year,
        month=month,
        transaction_count=row[0],
        expense_total=row[1],
        income_total=row[2],
        net_total=row[3],
        categories=categories,
        main_categories=main_categories,
        excluded_from_budget=excluded_from_budget,
    )


def get_transaction(transaction_id: int) -> Transaction | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, merchant, amount, transaction_date, main_category, category
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
                main_category = %s,
                category = %s
            WHERE id = %s
            RETURNING id, merchant, amount, transaction_date, main_category, category
            """,
            (
                transaction.merchant,
                transaction.amount,
                transaction.date,
                CATEGORY_PARENTS[transaction.category],
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
