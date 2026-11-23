from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from statistics import median

from .database import get_connection
from .schemas import (
    BankCategory,
    CATEGORY_PARENTS,
    CategoryTotal,
    EXCLUDED_MAIN_CATEGORY,
    ForecastCategory,
    ForecastMainCategory,
    ForecastExcludedExpense,
    MainCategoryTotal,
    MonthlyHistoryItem,
    MonthlyForecast,
    Transaction,
    TransactionCreate,
    TransactionHistory,
    TransactionSummary,
    TRANSFER_CATEGORIES,
    BillOccurrence,
    UpcomingBill,
    UpcomingBills,
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
            WITH reported_transactions AS (
                SELECT *,
                       CASE
                           WHEN amount > 0 AND category = %s
                                AND transaction_date >=
                                    (date_trunc('month', transaction_date)
                                     + interval '1 month' - interval '5 days')::date
                           THEN (transaction_date + interval '1 month')::date
                           ELSE transaction_date
                       END AS report_date
                FROM transactions
            )
            SELECT COUNT(*),
                   COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0),
                   COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0),
                   COALESCE(SUM(amount), 0)
            FROM reported_transactions
            WHERE report_date >= %s AND report_date < %s
              AND main_category <> %s
              AND category <> ALL(%s)
            """,
            (
                BankCategory.SALARY_PENSION_INCOME.value,
                start_date,
                next_month,
                EXCLUDED_MAIN_CATEGORY,
                list(TRANSFER_CATEGORIES),
            ),
        ).fetchone()
        category_rows = connection.execute(
            """
            WITH reported_transactions AS (
                SELECT *,
                       CASE
                           WHEN amount > 0 AND category = %s
                                AND transaction_date >=
                                    (date_trunc('month', transaction_date)
                                     + interval '1 month' - interval '5 days')::date
                           THEN (transaction_date + interval '1 month')::date
                           ELSE transaction_date
                       END AS report_date
                FROM transactions
            )
            SELECT main_category,
                   category,
                   COUNT(*),
                   COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0),
                   COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0),
                   COALESCE(SUM(amount), 0)
            FROM reported_transactions
            WHERE report_date >= %s AND report_date < %s
              AND category <> ALL(%s)
            GROUP BY main_category, category
            ORDER BY SUM(ABS(amount)) DESC, main_category, category
            """,
            (
                BankCategory.SALARY_PENSION_INCOME.value,
                start_date,
                next_month,
                list(TRANSFER_CATEGORIES),
            ),
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
            WITH reported_transactions AS (
                SELECT *,
                       CASE
                           WHEN amount > 0 AND category = %s
                                AND transaction_date >=
                                    (date_trunc('month', transaction_date)
                                     + interval '1 month' - interval '5 days')::date
                           THEN (transaction_date + interval '1 month')::date
                           ELSE transaction_date
                       END AS report_date
                FROM transactions
            )
            SELECT date_trunc('month', report_date)::date,
                   main_category,
                   category,
                   COUNT(*),
                   COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0),
                   COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0),
                   COALESCE(SUM(amount), 0)
            FROM reported_transactions
            WHERE transaction_date >= %s - interval '5 days'
              AND transaction_date < %s
              AND report_date >= %s AND report_date < %s
              AND category <> ALL(%s)
            GROUP BY 1, 2, 3
            ORDER BY 1, 2, 3
            """,
            (
                BankCategory.SALARY_PENSION_INCOME.value,
                from_date,
                to_date_exclusive,
                from_date,
                to_date_exclusive,
                list(TRANSFER_CATEGORIES),
            ),
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
    income_history_from = (
        date(history_from.year + 1, 1, 1)
        if history_from.month == 12
        else date(history_from.year, history_from.month + 1, 1)
    )
    # Forecast seasonal totals from matching calendar months when available.
    # The first history month is still omitted from income history because it may
    # be missing salary shifted from the month before the imported period.
    history_months: list[date] = []
    month_cursor = date(history_from.year, history_from.month, 1)
    while month_cursor <= history_to:
        history_months.append(month_cursor)
        month_cursor = (
            date(month_cursor.year + 1, 1, 1)
            if month_cursor.month == 12
            else date(month_cursor.year, month_cursor.month + 1, 1)
        )

    seasonal_expense_months = [
        month for month in history_months if month.month == forecast_month
    ]
    eligible_income_months = [
        month for month in history_months if month >= income_history_from
    ]
    seasonal_income_months = [
        month for month in eligible_income_months if month.month == forecast_month
    ]
    expense_seasonal = bool(seasonal_expense_months)
    income_seasonal = bool(seasonal_income_months)
    expense_months = seasonal_expense_months or history_months
    income_months = seasonal_income_months or eligible_income_months
    expense_months_used = len(expense_months)
    income_months_used = len(income_months)
    with get_connection() as connection:
        rows = connection.execute(
            """
            WITH reported_transactions AS (
                SELECT *,
                       CASE
                           WHEN amount > 0 AND category = %s
                                AND transaction_date >=
                                    (date_trunc('month', transaction_date)
                                     + interval '1 month' - interval '5 days')::date
                           THEN (transaction_date + interval '1 month')::date
                           ELSE transaction_date
                       END AS report_date
                FROM transactions
            )
            SELECT transaction_date, merchant, main_category, category, amount,
                   report_date
            FROM reported_transactions
            WHERE transaction_date >= %s - interval '5 days'
              AND transaction_date < %s
              AND report_date >= %s AND report_date < %s
              AND main_category <> %s
              AND category <> ALL(%s)
            ORDER BY main_category, category, transaction_date
            """,
            (
                BankCategory.SALARY_PENSION_INCOME.value,
                history_from,
                history_to + timedelta(days=1),
                history_from,
                history_to + timedelta(days=1),
                EXCLUDED_MAIN_CATEGORY,
                list(TRANSFER_CATEGORIES),
            ),
        ).fetchall()

    def monthly_average(value: Decimal, denominator: int) -> Decimal:
        if denominator == 0:
            return Decimal("0.00")
        return (value / Decimal(denominator)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    grouped_transactions: dict[tuple[str, str], list[tuple]] = {}
    for row in rows:
        grouped_transactions.setdefault((row[2], row[3]), []).append(row)

    # Sparse subcategories (for example, a single car purchase in
    # "Transport (Andet)") need the broader main-category history as context.
    main_category_expenses: dict[str, list[Decimal]] = {}
    for (main_category, _), transactions in grouped_transactions.items():
        main_category_expenses.setdefault(main_category, []).extend(
            abs(row[4]) for row in transactions if row[4] < 0
        )

    excluded_one_off_expenses: list[ForecastExcludedExpense] = []
    category_totals: list[tuple[str, str, Decimal, Decimal]] = []
    for (main_category, category), transactions in grouped_transactions.items():
        expense_rows = [row for row in transactions if row[4] < 0]
        expense_values = [abs(row[4]) for row in expense_rows]
        excluded_ids: set[int] = set()
        threshold: Decimal | None = None
        baseline_values = (
            expense_values
            if len(expense_values) >= 5
            else main_category_expenses.get(main_category, [])
        )
        if len(baseline_values) >= 5:
            typical = median(baseline_values)
            deviations = [abs(value - typical) for value in baseline_values]
            mad = median(deviations)
            threshold = max(
                typical * Decimal("5"),
                typical + Decimal("10000"),
                typical + mad * Decimal("4.4478"),
            )
            for row in expense_rows:
                expense_amount = abs(row[4])
                if expense_amount > threshold:
                    excluded_ids.add(id(row))
                    excluded_one_off_expenses.append(
                        ForecastExcludedExpense(
                            date=row[0],
                            merchant=row[1],
                            main_category=main_category,
                            category=category,
                            amount=expense_amount,
                            threshold=threshold.quantize(
                                Decimal("0.01"), rounding=ROUND_HALF_UP
                            ),
                        )
                    )

        expense_by_report_month: dict[date, Decimal] = {}
        for row in expense_rows:
            if id(row) in excluded_ids:
                continue
            report_month = date(row[5].year, row[5].month, 1)
            expense_by_report_month[report_month] = (
                expense_by_report_month.get(report_month, Decimal("0"))
                + abs(row[4])
            )
        expense_total = sum(
            (expense_by_report_month.get(month, Decimal("0")) for month in expense_months),
            Decimal("0"),
        )

        income_by_report_month: dict[date, Decimal] = {}
        if category in {
            BankCategory.SALARY_PENSION_INCOME.value,
            BankCategory.PUBLIC_BENEFITS.value,
        }:
            for row in transactions:
                if row[4] <= 0 or row[5] < income_history_from:
                    continue
                report_month = date(row[5].year, row[5].month, 1)
                income_by_report_month[report_month] = (
                    income_by_report_month.get(report_month, Decimal("0")) + row[4]
                )
        income_total = sum(
            (income_by_report_month.get(month, Decimal("0")) for month in income_months),
            Decimal("0"),
        )
        if expense_total or income_total:
            category_totals.append(
                (main_category, category, expense_total, income_total)
            )

    excluded_one_off_expenses.sort(key=lambda item: item.amount, reverse=True)
    categories = [
        ForecastCategory(
            main_category=main_category,
            category=category,
            expense_forecast=monthly_average(expense_total, expense_months_used),
            income_forecast=monthly_average(income_total, income_months_used),
            net_forecast=(
                monthly_average(income_total, income_months_used)
                - monthly_average(expense_total, expense_months_used)
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        )
        for main_category, category, expense_total, income_total in category_totals
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
        expense_months_used=expense_months_used,
        expense_seasonal=expense_seasonal,
        income_months_used=income_months_used,
        income_seasonal=income_seasonal,
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
        excluded_one_off_expenses=excluded_one_off_expenses,
    )


def find_upcoming_bills(as_of: date, days_ahead: int) -> UpcomingBills:
    """Estimate monthly recurring expenses from recent transactions."""
    history_start = as_of - timedelta(days=365)
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT account_ref, account_name, merchant, transaction_date,
                   amount, main_category, category
            FROM transactions
            WHERE transaction_date >= %s AND transaction_date <= %s
              AND amount < 0
              AND main_category <> %s
              AND category <> ALL(%s)
            ORDER BY transaction_date
            """,
            (
                history_start,
                as_of,
                EXCLUDED_MAIN_CATEGORY,
                list(TRANSFER_CATEGORIES),
            ),
        ).fetchall()

    grouped: dict[tuple[str, str], list[tuple]] = {}
    for row in rows:
        account_key = row[0] or row[1] or "ukendt konto"
        merchant_key = " ".join(row[2].casefold().split())
        grouped.setdefault((account_key, merchant_key), []).append(row)

    horizon = as_of + timedelta(days=days_ahead)
    previous_month_end = date(as_of.year, as_of.month, 1) - timedelta(days=1)
    freshness_start = date(previous_month_end.year, previous_month_end.month, 1)
    bills: list[UpcomingBill] = []
    for occurrences in grouped.values():
        occurrences.sort(key=lambda item: item[3])
        if len(occurrences) < 3:
            continue
        # Drop stale series if no payment appeared last month or this month.
        if occurrences[-1][3] < freshness_start:
            continue

        recent = occurrences[-4:]
        intervals = [
            (later[3] - earlier[3]).days
            for earlier, later in zip(recent, recent[1:])
        ]
        if not all(25 <= interval <= 35 for interval in intervals):
            continue

        average_interval = round(sum(intervals) / len(intervals))
        latest = occurrences[-1]
        expected_date = latest[3] + timedelta(days=average_interval)
        while expected_date <= as_of:
            expected_date += timedelta(days=average_interval)
        if expected_date > horizon:
            continue

        amount_samples = recent[-3:]
        estimated_amount = (
            sum((abs(item[4]) for item in amount_samples), Decimal("0"))
            / Decimal(len(amount_samples))
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        bills.append(
            UpcomingBill(
                merchant=latest[2],
                account_name=latest[1],
                main_category=latest[5],
                category=latest[6],
                expected_date=expected_date,
                estimated_amount=estimated_amount,
                occurrences=len(recent),
                average_interval_days=average_interval,
                recent_occurrences=[
                    BillOccurrence(date=item[3], amount=abs(item[4]))
                    for item in recent
                ],
            )
        )

    bills.sort(key=lambda bill: (bill.expected_date, bill.merchant.casefold()))
    estimated_total = sum(
        (bill.estimated_amount for bill in bills), Decimal("0")
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return UpcomingBills(
        as_of=as_of,
        days_ahead=days_ahead,
        estimated_total=estimated_total,
        bills=bills,
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
