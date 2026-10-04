from pathlib import Path
import pandas as pd

# Find the project root automatically.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Define raw and processed data directories.
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "dnemis" / "2024_2025"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "dnemis" / "2024_2025"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Map raw DNEMIS school-type values to our standard project categories.
SCHOOL_TYPE_MAP = {
    "Pre2/Primary": "Primary",
    "JSS": "JSS",
    "SSS": "SSS",
    "TECH/VOC": "Tech/Voc",
    "IQS/IQTE": "IQS",
}

def load_source_tables():
    """Load the raw DNEMIS tables needed for transformation."""
    dx_df = pd.read_parquet(RAW_DIR / "dx.parquet")
    ou_df = pd.read_parquet(RAW_DIR / "ou.parquet")
    pe_df = pd.read_parquet(RAW_DIR / "pe.parquet")
    fact_df = pd.read_parquet(RAW_DIR / "fact_typeown.parquet")
    return dx_df, ou_df, pe_df, fact_df

def clean_geo_name(value):
    """Remove the two-letter DNEMIS prefix from geography names when present."""
    if pd.isna(value):
        return value
    parts = value.split(" ", 1)
    if len(parts) == 2 and len(parts[0]) == 2 and parts[0].isalpha():
        return parts[1]
    return value

def prepare_geography(ou_df):
    """Keep only LGA-level geography and create clean state/LGA names."""
    lga_df = ou_df[ou_df["level"] == 3].copy()
    lga_df = lga_df.rename(
        columns={
            "id": "ou",
            "name": "lga_raw",
            "parent_name": "state_raw",
        }
    )
    lga_df["lga"] = (
        lga_df["lga_raw"]
        .apply(clean_geo_name)
        .str.replace(r"\s+LGA$", "", regex=True)
        .str.strip()
    )
    lga_df["state"] = (
        lga_df["state_raw"]
        .apply(clean_geo_name)
        .str.replace(r"\s+State$", "", regex=True)
        .str.strip()
    )
    return lga_df[["ou", "state", "lga", "state_raw", "lga_raw"]]

def prepare_indicators(dx_df):
    """Rename the indicator dictionary into analysis-friendly fields."""
    indicators = dx_df.rename(
        columns={
            "id": "dx",
            "name": "indicator",
        }
    ).copy()
    return indicators[["dx", "indicator"]]

def build_long_dataset(fact_df, indicator_df, geography_df):
    """Join the fact table to indicator and geography dimensions."""
    df = fact_df.copy()
    df = df.merge(
        indicator_df,
        on="dx",
        how="left",
        validate="many_to_one",
    )
    df = df.merge(
        geography_df,
        on="ou",
        how="inner",
        validate="many_to_one",
    )
    return df

def normalize_categories(df):
    """Standardize school type and ownership categories and flag anomalies."""
    df = df.copy()
    df["education_level"] = df["cat1_name"].map(SCHOOL_TYPE_MAP)
    df["ownership"] = df["cat2_name"]
    df["invalid_school_type"] = df["education_level"].isna()
    df["invalid_ownership"] = ~df["ownership"].isin(["Public", "Private"])
    return df

def select_clean_columns(df):
    """Keep only the fields needed for downstream analysis."""
    clean_df = df[
        [
            "pe",
            "state",
            "lga",
            "education_level",
            "ownership",
            "indicator",
            "value",
            "invalid_school_type",
            "invalid_ownership",
        ]
    ].copy()
    clean_df = clean_df.rename(columns={"pe": "year"})
    return clean_df

def main():
    """Run the DNEMIS transformation pipeline."""
    print("Loading raw tables...")
    dx_df, ou_df, pe_df, fact_df = load_source_tables()
    print("Preparing dimensions...")
    geography_df = prepare_geography(ou_df)
    indicator_df = prepare_indicators(dx_df)
    print("Joining fact table...")
    transformed = build_long_dataset(
        fact_df,
        indicator_df,
        geography_df,
    )
    print("Normalizing categories...")
    transformed = normalize_categories(transformed)
    clean_long = select_clean_columns(transformed)
    output_path = PROCESSED_DIR / "education_capacity_long.parquet"
    clean_long.to_parquet(output_path, index=False)
    print(f"Saved transformed data to: {output_path}")
    print("Rows:", len(clean_long))
    print("\nEducation levels:")
    print(clean_long["education_level"].value_counts(dropna=False))
    print("\nOwnership:")
    print(clean_long["ownership"].value_counts(dropna=False))

if __name__ == "__main__":
    main()