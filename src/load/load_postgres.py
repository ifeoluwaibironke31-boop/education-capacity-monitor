from pathlib import Path
import os
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "dnemis" / "2024_2025"

CAPACITY_PATH = PROCESSED_DIR / "education_capacity_wide.parquet"
REPORTING_PATH = PROCESSED_DIR / "reporting_metrics.parquet"

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "education_capacity")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_SSLMODE = os.getenv("DB_SSLMODE") or os.getenv("PGSSLMODE")


def get_engine():
    if not DB_PASSWORD:
        raise ValueError("DB_PASSWORD environment variable is not set.")

    url = URL.create(
        "postgresql+psycopg2",
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
    )

    connect_args = {"sslmode": DB_SSLMODE} if DB_SSLMODE else {}
    return create_engine(url, connect_args=connect_args)


def load_table(engine, parquet_path, table_name):
    if not parquet_path.exists():
        raise FileNotFoundError(f"Missing processed file: {parquet_path}")

    df = pd.read_parquet(parquet_path)

    print(f"\nLoading {table_name}...")
    print(f"Source rows: {len(df):,}")

    df.to_sql(
        table_name,
        engine,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=1000,
    )

    with engine.connect() as connection:
        loaded_rows = connection.execute(
            text(f'SELECT COUNT(*) FROM "{table_name}"')
        ).scalar_one()

    if loaded_rows != len(df):
        raise RuntimeError(
            f"{table_name} row-count mismatch: "
            f"expected {len(df):,}, loaded {loaded_rows:,}"
        )

    print(f"Loaded successfully: {loaded_rows:,} rows")


def main():
    engine = get_engine()

    try:
        load_table(
            engine,
            CAPACITY_PATH,
            "capacity_metrics",
        )

        load_table(
            engine,
            REPORTING_PATH,
            "reporting_metrics",
        )

        print("\nPostgreSQL load completed successfully.")

        with engine.connect() as connection:
            capacity_count = connection.execute(
                text("SELECT COUNT(*) FROM capacity_metrics")
            ).scalar_one()

            reporting_count = connection.execute(
                text("SELECT COUNT(*) FROM reporting_metrics")
            ).scalar_one()

        print(f"capacity_metrics: {capacity_count:,}")
        print(f"reporting_metrics: {reporting_count:,}")

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()