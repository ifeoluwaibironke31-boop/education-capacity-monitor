from pathlib import Path
import pandas as pd

# Find the project root automatically.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Define raw and processed data directories.
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "dnemis" / "2024_2025"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "dnemis" / "2024_2025"

# Create the processed directory if it does not already exist.
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Map raw DNEMIS school-type values to the categories used in this project.
SCHOOL_TYPE_MAP = {
    "Pre2/Primary": "Primary",
    "JSS": "JSS",
    "SSS": "SSS",
    "TECH/VOC": "Tech/Voc",
    "IQS/IQTE": "IQS",
}

def load_source_tables():
    """Load the raw DNEMIS tables required for transformation."""
    dx_df = pd.read_parquet(
        RAW_DIR / "dx.parquet"
    )

    ou_df = pd.read_parquet(
        RAW_DIR / "ou.parquet"
    )

    pe_df = pd.read_parquet(
        RAW_DIR / "pe.parquet"
    )

    fact_df = pd.read_parquet(
        RAW_DIR / "fact_typeown.parquet"
    )

    return dx_df, ou_df, pe_df, fact_df

def clean_geo_name(value):
    """Remove the two-letter DNEMIS prefix from geography names."""
    if pd.isna(value):
        return value

    parts = value.split(" ", 1)

    # DNEMIS geography names contain prefixes such as:
    # "la Lagos State" or "la Ikeja LGA".
    if (
        len(parts) == 2
        and len(parts[0]) == 2
        and parts[0].isalpha()
    ):
        return parts[1]

    return value

def prepare_geography(ou_df):
    """Prepare state and LGA names from the DNEMIS geography table."""
    # Level 3 represents LGAs.
    geography = ou_df[
        ou_df["level"] == 3
    ].copy()

    geography = geography.rename(
        columns={
            "id": "ou",
            "name": "lga_raw",
            "parent_name": "state_raw",
        }
    )

    # Remove the DNEMIS two-letter geography prefixes.
    geography["lga"] = (
        geography["lga_raw"]
        .apply(clean_geo_name)
    )

    geography["state"] = (
        geography["state_raw"]
        .apply(clean_geo_name)
    )

    # Remove the trailing "LGA" label.
    geography["lga"] = (
        geography["lga"]
        .str.replace(
            r"\s+LGA$",
            "",
            regex=True,
        )
        .str.strip()
    )

    # Remove the trailing "State" label.
    geography["state"] = (
        geography["state"]
        .str.replace(
            r"\s+State$",
            "",
            regex=True,
        )
        .str.strip()
    )

    # Keep the geography fields needed for downstream joins and analysis.
    return geography[
        [
            "ou",
            "state",
            "lga",
            "state_raw",
            "lga_raw",
        ]
    ]

def prepare_indicators(dx_df):
    """Prepare the indicator dictionary for joining to the fact table."""
    indicators = dx_df.rename(
        columns={
            "id": "dx",
            "name": "indicator",
        }
    ).copy()

    return indicators[
        [
            "dx",
            "indicator",
        ]
    ]

def build_long_dataset(
    fact_df,
    indicator_df,
    geography_df,
):
    """Join the fact table with indicator and geography dimensions."""
    df = fact_df.copy()

    # Add readable indicator names.
    df = df.merge(
        indicator_df,
        on="dx",
        how="left",
        validate="many_to_one",
    )

    # Add state and LGA information.
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

    # Convert raw DNEMIS school-type labels into project-standard values.
    df["education_level"] = (
        df["cat1_name"]
        .map(SCHOOL_TYPE_MAP)
    )

    # Ownership values are already readable in DNEMIS.
    df["ownership"] = df["cat2_name"]

    # Flag unexpected school-type values instead of silently deleting them.
    df["invalid_school_type"] = (
        df["education_level"].isna()
    )

    # Flag unexpected ownership values instead of deleting them.
    df["invalid_ownership"] = ~df[
        "ownership"
    ].isin(
        [
            "Public",
            "Private",
        ]
    )

    return df

def select_clean_columns(df):
    """Keep only the fields required by downstream analysis."""
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

    # Rename the DNEMIS reporting-period field to a clearer name.
    clean_df = clean_df.rename(
        columns={
            "pe": "year",
        }
    )

    return clean_df

def main():
    """Run the DNEMIS transformation pipeline."""
    print("Loading raw tables...")

    dx_df, ou_df, pe_df, fact_df = load_source_tables()

    print("Preparing geography...")

    geography_df = prepare_geography(
        ou_df
    )

    print("Preparing indicators...")

    indicator_df = prepare_indicators(
        dx_df
    )

    print("Joining fact table...")

    transformed = build_long_dataset(
        fact_df,
        indicator_df,
        geography_df,
    )

    print("Normalizing categories...")

    transformed = normalize_categories(
        transformed
    )

    print("Selecting clean columns...")

    clean_long = select_clean_columns(
        transformed
    )

    output_path = (
        PROCESSED_DIR
        / "education_capacity_long.parquet"
    )

    clean_long.to_parquet(
        output_path,
        index=False,
    )

    print(
        f"Saved transformed data to: {output_path}"
    )

    print(
        f"Rows: {len(clean_long):,}"
    )

    print("\nColumns:")
    print(
        clean_long.columns.tolist()
    )

    print("\nEducation levels:")
    print(
        clean_long[
            "education_level"
        ].value_counts(
            dropna=False
        )
    )

    print("\nOwnership:")
    print(
        clean_long[
            "ownership"
        ].value_counts(
            dropna=False
        )
    )

    print("\nInvalid school-type rows:")
    print(
        clean_long[
            "invalid_school_type"
        ].sum()
    )

    print("\nInvalid ownership rows:")
    print(
        clean_long[
            "invalid_ownership"
        ].sum()
    )

if __name__ == "__main__":
    main()