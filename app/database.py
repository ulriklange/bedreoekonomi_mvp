from contextlib import asynccontextmanager
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.conninfo import make_conninfo
from .schemas import CATEGORY_PARENTS


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


def get_connection():
    """Open a connection to the Lakebase Postgres database."""
    return psycopg.connect(DB_CONNECTION)


def ensure_schema(connection) -> None:
    """Create or migrate the transaction table to the current schema."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id BIGSERIAL PRIMARY KEY,
            merchant TEXT NOT NULL,
            amount NUMERIC(10, 2) NOT NULL,
            transaction_date DATE NOT NULL,
            main_category TEXT NOT NULL,
            category TEXT NOT NULL,
            source_fingerprint TEXT,
            account_ref TEXT,
            account_name TEXT
        )
        """
    )
    connection.execute(
        "ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_amount_check"
    )
    connection.execute(
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS main_category TEXT"
    )
    connection.execute(
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS source_fingerprint TEXT"
    )
    connection.execute(
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS account_ref TEXT"
    )
    connection.execute(
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS account_name TEXT"
    )
    for category, main_category in CATEGORY_PARENTS.items():
        connection.execute(
            "UPDATE transactions SET main_category = %s "
            "WHERE category = %s AND main_category IS NULL",
            (main_category, category.value),
        )
    connection.execute(
        "UPDATE transactions SET main_category = 'Ukategoriseret' "
        "WHERE main_category IS NULL"
    )
    connection.execute(
        "ALTER TABLE transactions ALTER COLUMN main_category SET NOT NULL"
    )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS transactions_source_fingerprint_key "
        "ON transactions (source_fingerprint)"
    )


@asynccontextmanager
async def lifespan(app):
    """Create or migrate the transaction table when the API starts."""
    with get_connection() as connection:
        ensure_schema(connection)
    yield
