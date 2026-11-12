from contextlib import asynccontextmanager
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.conninfo import make_conninfo


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


@asynccontextmanager
async def lifespan(app):
    """Create the transactions table when the API starts, if needed."""
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id BIGSERIAL PRIMARY KEY,
                merchant TEXT NOT NULL,
                amount NUMERIC(10, 2) NOT NULL,
                transaction_date DATE NOT NULL,
                category TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_amount_check"
        )
    yield
