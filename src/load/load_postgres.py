from pathlib import Path
import os
import pandas as pd
from sqlalchemy import create_engine, text

# Find the project root automatically.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Location of the processed analytical dataset.
DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "dnemis"
    / "2024_2025"
    / "education_capacity_wide.parquet"
)

# Read PostgreSQL connection details from environment variables.
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "education_capacity")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")

def create_db_engine():
    """Create a SQLAlchemy connection to PostgreSQL."""
    if not DB_PASSWORD:
        raise ValueError(
            "DB_PASSWORD is not set. "
            "Set it as an environment variable before running this script."
        )

    connection_url = (
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    return create_engine(connection_url)

def load_capacity_data(engine):
    """Load the processed capacity dataset into PostgreSQL."""
    df = pd.read_parquet(DATA_PATH)

    # Replace the existing table so repeated pipeline runs remain reproducible.
    df.to_sql(
        "capacity_metrics",
        engine,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=1000,
    )

    return len(df)

def verify_load(engine):
    """Confirm that rows were successfully written to PostgreSQL."""
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT COUNT(*) FROM capacity_metrics")
        )

        return result.scalar()

def main():
    """Connect to PostgreSQL, load the dataset, and verify the result."""
    print("Connecting to PostgreSQL...")
    engine = create_db_engine()

    print("Loading capacity data...")
    rows_loaded = load_capacity_data(engine)

    print("Verifying load...")
    rows_in_database = verify_load(engine)

    print(f"Rows loaded from Parquet: {rows_loaded:,}")
    print(f"Rows found in PostgreSQL: {rows_in_database:,}")
    print("PostgreSQL load complete.")

if __name__ == "__main__":
    main()