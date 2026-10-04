# Import Path so we can build file paths safely across operating systems.
from pathlib import Path
# Pandas will be used to load and inspect the Parquet datasets.
import pandas as pd
# Locate the root of the project automatically.
# __file__ is this script:
# src/validate/validate_dnemis.py
#
# parents[2] moves us back to:
# education-capacity-monitor/
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Define where the raw DNEMIS files are stored.
RAW_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "dnemis"
    / "2024_2025"
)
# Define the minimum columns that we expect each raw source file to contain.
#
# We use sets here because the order of the columns does not matter.
# What matters is whether the required columns are present.
EXPECTED_COLUMNS = {
    "dx.parquet": {
        "id",
        "name",
    },
    "ou.parquet": {
        "id",
        "name",
        "level",
        "parent_id",
        "parent_name",
        "path",
    },
    "pe.parquet": {
        "period",
        "periodType",
        "year",
        "startDate",
    },
    "constants.parquet": {
        "id",
        "name",
        "value",
    },
    "fact_typeown.parquet": {
        "dx",
        "ou",
        "pe",
        "periodType",
        "cat1_id",
        "cat1_name",
        "cat2_id",
        "cat2_name",
        "value",
    },
}
def load_raw_tables() -> dict[str, pd.DataFrame]:
    """
    Load all required DNEMIS raw Parquet files into pandas DataFrames.
    Returns:
        A dictionary where:
        - the key is the file name
        - the value is the loaded DataFrame
    """
    tables = {}
    # Loop through every file listed in EXPECTED_COLUMNS.
    for file_name in EXPECTED_COLUMNS:
        path = RAW_DIR / file_name
        # Stop immediately if one of the required raw files is missing.
        if not path.exists():
            raise FileNotFoundError(
                f"Missing raw file: {path}"
            )
        # Load the Parquet file into memory.
        tables[file_name] = pd.read_parquet(path)
    return tables
def validate_columns(
    df: pd.DataFrame,
    file_name: str,
) -> list[str]:
    """
    Check whether a DataFrame contains all required columns.
    Returns:
        A list of validation error messages.
        An empty list means no column errors were found.
    """
    errors = []
    # Required columns for this specific file.
    expected = EXPECTED_COLUMNS[file_name]
    # Actual columns found in the DataFrame.
    actual = set(df.columns)
    # Find any required columns that are missing.
    missing = expected - actual
    if missing:
        errors.append(
            f"{file_name} is missing columns: "
            f"{sorted(missing)}"
        )
    return errors
def validate_geography(
    ou_df: pd.DataFrame,
) -> list[str]:
    """
    Validate the known Nigerian geographic hierarchy.
    Based on our source discovery, DNEMIS currently contains:
    - 1 national unit
    - 37 state/FCT units
    - 774 LGAs
    """
    errors = []
    # Count the number of organisation units at each hierarchy level.
    level_counts = (
        ou_df["level"]
        .value_counts()
        .to_dict()
    )
    # Level 1 should contain Nigeria only.
    if level_counts.get(1.0, 0) != 1:
        errors.append(
            "Expected exactly 1 national unit."
        )
    # Level 2 should contain 36 states + FCT.
    if level_counts.get(2.0, 0) != 37:
        errors.append(
            "Expected exactly 37 state/FCT units."
        )
    # Level 3 should contain all Nigerian LGAs.
    if level_counts.get(3.0, 0) != 774:
        errors.append(
            "Expected exactly 774 LGAs."
        )
    return errors
def validate_foreign_keys(
    fact_df: pd.DataFrame,
    dx_df: pd.DataFrame,
    ou_df: pd.DataFrame,
) -> list[str]:
    """
    Check that IDs used in the fact table exist
    in the corresponding dimension tables.
    """
    errors = []
    # Valid indicator IDs.
    valid_dx = set(dx_df["id"])
    # Valid organisation-unit IDs.
    valid_ou = set(ou_df["id"])
    # IDs present in the fact table but missing from dx.parquet.
    invalid_dx = set(fact_df["dx"]) - valid_dx
    # IDs present in the fact table but missing from ou.parquet.
    invalid_ou = set(fact_df["ou"]) - valid_ou
    if invalid_dx:
        errors.append(
            f"Found {len(invalid_dx)} unknown dx IDs."
        )
    if invalid_ou:
        errors.append(
            f"Found {len(invalid_ou)} unknown ou IDs."
        )
    return errors
def validate_values(
    fact_df: pd.DataFrame,
) -> list[str]:
    """
    Check for obviously invalid numeric values.
    For this first version, negative values are treated
    as errors because counts and ratios in this source
    should not normally be negative.
    """
    errors = []
    negative_values = fact_df[
        fact_df["value"] < 0
    ]
    if not negative_values.empty:
        errors.append(
            f"Found {len(negative_values)} negative fact values."
        )
    return errors
# Expected education-level categories discovered in DNEMIS.
VALID_SCHOOL_TYPES = {
    "Pre2/Primary",
    "JSS",
    "SSS",
    "TECH/VOC",
    "IQS/IQTE",
}
# Expected ownership categories.
VALID_OWNERSHIP = {
    "Public",
    "Private",
}
def find_warnings(
    fact_df: pd.DataFrame,
) -> list[str]:
    """
    Find unusual source values that should be reviewed
    but should not cause the validation pipeline to fail.
    """
    warnings = []
    # Collect all school-type values present in the source.
    school_types = set(
        fact_df["cat1_name"]
        .dropna()
        .unique()
    )
    # Anything outside our expected list is suspicious.
    unexpected_school_types = (
        school_types - VALID_SCHOOL_TYPES
    )
    if unexpected_school_types:
        warnings.append(
            "Unexpected school types: "
            f"{sorted(unexpected_school_types)}"
        )
    # Collect all ownership values.
    ownership_values = set(
        fact_df["cat2_name"]
        .dropna()
        .unique()
    )
    # Anything outside Public/Private should be reviewed.
    unexpected_ownership = (
        ownership_values - VALID_OWNERSHIP
    )
    if unexpected_ownership:
        warnings.append(
            "Unexpected ownership values: "
            f"{sorted(unexpected_ownership)}"
        )
    return warnings
def main():
    """
    Run all raw-data validation checks.
    """
    # Load all raw source tables.
    tables = load_raw_tables()
    all_errors = []
    all_warnings = []
    # Validate required columns for every table.
    for file_name, df in tables.items():
        all_errors.extend(
            validate_columns(
                df,
                file_name,
            )
        )
    # Give the main tables shorter variable names.
    dx_df = tables["dx.parquet"]
    ou_df = tables["ou.parquet"]
    fact_df = tables["fact_typeown.parquet"]
    # Validate the geography hierarchy.
    all_errors.extend(
        validate_geography(ou_df)
    )
    # Validate indicator and geography references.
    all_errors.extend(
        validate_foreign_keys(
            fact_df,
            dx_df,
            ou_df,
        )
    )
    # Validate numeric values.
    all_errors.extend(
        validate_values(fact_df)
    )
    # Collect non-fatal source anomalies.
    all_warnings.extend(
        find_warnings(fact_df)
    )
    # Print a readable validation report.
    print("\nVALIDATION RESULTS")
    print("------------------")
    if all_errors:
        print("\nERRORS:")
        for error in all_errors:
            print(f"- {error}")
    else:
        print("\nNo validation errors.")
    if all_warnings:
        print("\nWARNINGS:")
        for warning in all_warnings:
            print(f"- {warning}")
    else:
        print("\nNo validation warnings.")
    # Fail the script only when real validation errors exist.
    if all_errors:
        raise ValueError(
            "Validation failed."
        )
    print("\nValidation passed.")
# This block runs main() only when this file is executed directly.
if __name__ == "__main__":
    main()