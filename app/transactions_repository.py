from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from .database import get_connection
from .schemas import (
    CATEGORY_PARENTS,
    CategoryTotal,
    EXCLUDED_MAIN_CATEGORY,
    ForecastCategory,
    ForecastMainCategory,
    MainCategoryTotal,
    MonthlyHistoryItem,
    MonthlyForecast,
    Transaction,
    TransactionCreate,
    TransactionHistory,
    TransactionSummary,
    TRANSFER_CATEGORIES,
)


def _to_transaction(row) -> Transaction:
    return Transaction(
        id=row[0],
        merchant=row[1],
        amount=row[2],
        date=row[3],
        main_category=row[4],
        category=row[5],
        account_name=row[6],
    )


def create_transaction(transaction: TransactionCreate) -> Transaction:
    with get_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO transactions
                (merchant, amount, transaction_date, main_category, category,
                 account_name)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, merchant, amount, transaction_date, main_category,
                      category, account_name
            """,
            (
                transaction.merchant,
                transaction.amount,
                transaction.date,
                CATEGORY_PARENTS[transaction.category],
                transaction.category.value,
                transaction.account_name,
            ),
        ).fetchone()

    return _to_transaction(row)


def list_transactions(category: str | None = None) -> list[Transaction]:
    query = """
        SELECT id, merchant, amount, transaction_date, main_category, category,
               account_name
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
              AND category <> ALL(%s)
            """,
            (
                start_date,
                next_month,
                EXCLUDED_MAIN_CATEGORY,
                list(TRANSFER_CATEGORIES),
            ),
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
              AND category <> ALL(%s)
            GROUP BY main_category, category
            ORDER BY SUM(ABS(amount)) DESC, main_category, category
            """,
            (start_date, next_month, list(TRANSFER_CATEGORIES)),
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


def get_monthly_history(from_date: date, to_date: date) -> TransactionHistory:
    """Return calendar-month totals for a requested inclusive date range."""
    to_date_exclusive = to_date + timedelta(days=1)
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT date_trunc('month', transaction_date)::date,
                   main_category,
                   category,
                   COUNT(*),
                   COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0),
                   COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0),
                   COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE transaction_date >= %s AND transaction_date < %s
              AND category <> ALL(%s)
            GROUP BY 1, 2, 3
            ORDER BY 1, 2, 3
            """,
            (from_date, to_date_exclusive, list(TRANSFER_CATEGORIES)),
        ).fetchall()

    rows_by_month: dict[date, list[tuple]] = {}
    for row in rows:
        rows_by_month.setdefault(row[0], []).append(row)

    month_starts: list[date] = []
    cursor_month = date(from_date.year, from_date.month, 1)
    last_month = date(to_date.year, to_date.month, 1)
    while cursor_month <= last_month:
        month_starts.append(cursor_month)
        if cursor_month.month == 12:
            cursor_month = date(cursor_month.year + 1, 1, 1)
        else:
            cursor_month = date(cursor_month.year, cursor_month.month + 1, 1)

    months: list[MonthlyHistoryItem] = []
    for month_start in month_starts:
        grouped_rows = rows_by_month.get(month_start, [])
        categories = [
            CategoryTotal(
                main_category=row[1],
                category=row[2],
                transaction_count=row[3],
                expense_total=row[4],
                income_total=row[5],
                net_total=row[6],
            )
            for row in grouped_rows
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

        excluded_values = parent_totals.pop(EXCLUDED_MAIN_CATEGORY, None)
        excluded = (
            MainCategoryTotal(
                main_category=EXCLUDED_MAIN_CATEGORY,
                **excluded_values,
            )
            if excluded_values is not None
            else None
        )
        main_categories = [
            MainCategoryTotal(main_category=name, **totals)
            for name, totals in sorted(
                parent_totals.items(),
                key=lambda item: item[1]["expense_total"] + item[1]["income_total"],
                reverse=True,
            )
        ]
        summary_totals = {
            "transaction_count": sum(
                item.transaction_count for item in main_categories
            ),
            "expense_total": sum(
                (item.expense_total for item in main_categories), Decimal("0")
            ),
            "income_total": sum(
                (item.income_total for item in main_categories), Decimal("0")
            ),
            "net_total": sum(
                (item.net_total for item in main_categories), Decimal("0")
            ),
        }

        if month_start.month == 12:
            next_month_start = date(month_start.year + 1, 1, 1)
        else:
            next_month_start = date(month_start.year, month_start.month + 1, 1)
        partial_month = (
            from_date > month_start or to_date_exclusive < next_month_start
        )
        months.append(
            MonthlyHistoryItem(
                year=month_start.year,
                month=month_start.month,
                partial_month=partial_month,
                **summary_totals,
                main_categories=main_categories,
                excluded_from_budget=excluded,
            )
        )

    return TransactionHistory(
        from_date=from_date,
        to_date=to_date,
        months=months,
    )


def forecast_monthly(
    forecast_year: int,
    forecast_month: int,
    history_from: date,
    history_to: date,
) -> MonthlyForecast:
    """Forecast a month using average totals over complete historical months."""
    months_used = (
        (history_to.year - history_from.year) * 12
        + history_to.month
        - history_from.month
        + 1
    )
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT main_category,
                   category,
                   COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0),
                   COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0),
                   COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE transaction_date >= %s AND transaction_date < %s
              AND main_category <> %s
              AND category <> ALL(%s)
            GROUP BY main_category, category
            ORDER BY main_category, category
            """,
            (
                history_from,
                history_to + timedelta(days=1),
                EXCLUDED_MAIN_CATEGORY,
                list(TRANSFER_CATEGORIES),
            ),
        ).fetchall()

    def monthly_average(value: Decimal) -> Decimal:
        return (value / Decimal(months_used)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    categories = [
        ForecastCategory(
            main_category=row[0],
            category=row[1],
            expense_forecast=monthly_average(row[2]),
            income_forecast=monthly_average(row[3]),
            net_forecast=monthly_average(row[4]),
        )
        for row in rows
    ]
    parent_totals: dict[str, dict] = {}
    for category in categories:
        totals = parent_totals.setdefault(
            category.main_category,
            {
                "expense_forecast": Decimal("0"),
                "income_forecast": Decimal("0"),
                "net_forecast": Decimal("0"),
                "subcategories": [],
            },
        )
        totals["expense_forecast"] += category.expense_forecast
        totals["income_forecast"] += category.income_forecast
        totals["net_forecast"] += category.net_forecast
        totals["subcategories"].append(category)

    main_categories = [
        ForecastMainCategory(main_category=name, **totals)
        for name, totals in sorted(
            parent_totals.items(),
            key=lambda item: (
                item[1]["expense_forecast"] + item[1]["income_forecast"]
            ),
            reverse=True,
        )
    ]

    return MonthlyForecast(
        forecast_year=forecast_year,
        forecast_month=forecast_month,
        history_from=history_from,
        history_to=history_to,
        months_used=months_used,
        expense_forecast=sum(
            (item.expense_forecast for item in main_categories), Decimal("0")
        ),
        income_forecast=sum(
            (item.income_forecast for item in main_categories), Decimal("0")
        ),
        net_forecast=sum(
            (item.net_forecast for item in main_categories), Decimal("0")
        ),
        main_categories=main_categories,
    )


def get_transaction(transaction_id: int) -> Transaction | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, merchant, amount, transaction_date, main_category, category,
                   account_name
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
                category = %s,
                account_name = COALESCE(%s, account_name)
            WHERE id = %s
            RETURNING id, merchant, amount, transaction_date, main_category, category,
                      account_name
            """,
            (
                transaction.merchant,
                transaction.amount,
                transaction.date,
                CATEGORY_PARENTS[transaction.category],
                transaction.category.value,
                transaction.account_name,
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
