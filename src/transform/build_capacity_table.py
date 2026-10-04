from pathlib import Path
import pandas as pd

# Find the project root automatically.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Define input and output locations.
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "dnemis" / "2024_2025"
INPUT_PATH = PROCESSED_DIR / "education_capacity_long.parquet"
OUTPUT_PATH = PROCESSED_DIR / "education_capacity_wide.parquet"

# Core indicators used for teacher-distribution and classroom-overcrowding analysis.
CORE_INDICATORS = {
    "ASC-GEN Enrolment (all levels)": "learners",
    "MD: Total teachers": "teachers",
    "ASC-GEN Learner-teacher ratio (ratio)": "source_learner_teacher_ratio",
    "Learners per classroom(subex)": "learners_per_classroom",
}

def load_data():
    """Load the transformed long-format DNEMIS dataset."""
    return pd.read_parquet(INPUT_PATH)

def filter_core_data(df):
    """Keep valid rows for the four indicators required by the MVP."""
    return df[
        df["indicator"].isin(CORE_INDICATORS)
        & df["education_level"].notna()
        & df["ownership"].isin(["Public", "Private"])
    ].copy()

def build_wide_table(core_df):
    """Pivot indicator values into separate analytical columns."""
    wide_df = (
        core_df
        .pivot_table(
            index=[
                "year",
                "state",
                "lga",
                "education_level",
                "ownership",
            ],
            columns="indicator",
            values="value",
            aggfunc="first",
        )
        .reset_index()
    )

    # Rename source indicator names to shorter analysis-friendly names.
    wide_df = wide_df.rename(columns=CORE_INDICATORS)
    wide_df.columns.name = None
    return wide_df

def add_completeness_flags(df):
    """Flag whether each row contains every required core indicator."""
    df = df.copy()

    required_columns = [
        "learners",
        "teachers",
        "source_learner_teacher_ratio",
        "learners_per_classroom",
    ]

    df["is_complete"] = df[required_columns].notna().all(axis=1)
    df["missing_metric_count"] = df[required_columns].isna().sum(axis=1)
    return df

def add_teacher_metrics(df):
    """Calculate teacher-capacity metrics and compare them with the DNEMIS source ratio."""
    df = df.copy()

    # UBE learner-teacher benchmark from DNEMIS constants.parquet.
    teacher_standard = 35.0

    # Independently calculate the ratio for quality-control purposes.
    df["calculated_learner_teacher_ratio"] = (
        df["learners"] / df["teachers"].replace(0, pd.NA)
    )

    # Measure disagreement between our calculation and the DNEMIS source ratio.
    df["teacher_ratio_difference"] = (
        df["calculated_learner_teacher_ratio"]
        - df["source_learner_teacher_ratio"]
    ).abs()

    # Use DNEMIS's published ratio as the primary pressure metric.
    df["teacher_pressure_index"] = (
        df["source_learner_teacher_ratio"] / teacher_standard
    )

    # Estimate teacher requirement at the benchmark ratio.
    df["required_teachers"] = df["learners"] / teacher_standard

    # Positive values represent an estimated teacher shortfall.
    df["teacher_gap"] = (
        df["required_teachers"] - df["teachers"]
    ).clip(lower=0)

    # Preserve unusually high values but flag them for review.
    df["extreme_teacher_ratio"] = (
        df["source_learner_teacher_ratio"] > 100
    )

    # Flag material disagreement between our calculated ratio and the source ratio.
    df["teacher_ratio_mismatch"] = (
        df["teacher_ratio_difference"] > 5
    )

    return df

def add_classroom_metrics(df):
    """Calculate classroom-pressure metrics from the DNEMIS source ratio."""
    df = df.copy()

    # UBE learner-classroom benchmark from DNEMIS constants.parquet.
    classroom_standard = 35.0

    # Values above 1 indicate classroom pressure above the benchmark.
    df["classroom_pressure_index"] = (
        df["learners_per_classroom"] / classroom_standard
    )

    # Show how far the classroom ratio exceeds the benchmark.
    df["classroom_ratio_gap"] = (
        df["learners_per_classroom"] - classroom_standard
    ).clip(lower=0)

    # Preserve extreme observations but flag them for review.
    df["extreme_classroom_ratio"] = (
        df["learners_per_classroom"] > 100
    )

    return df

def add_priority_flags(df):
    """Create dashboard warning flags for teacher and classroom pressure."""
    df = df.copy()

    # Teacher warning based on the DNEMIS source learner-teacher ratio.
    df["teacher_warning"] = (
        df["source_learner_teacher_ratio"] > 35
    )

    # Classroom warning based on the DNEMIS learners-per-classroom ratio.
    df["classroom_warning"] = (
        df["learners_per_classroom"] > 35
    )

    # Count how many capacity problems affect each record.
    df["capacity_warning_count"] = (
        df["teacher_warning"].fillna(False).astype(int)
        + df["classroom_warning"].fillna(False).astype(int)
    )

    return df

def main():
    """Build and save the final education-capacity analytical table."""
    print("Loading transformed data...")
    df = load_data()

    print("Filtering core indicators...")
    core_df = filter_core_data(df)

    print("Building wide analytical table...")
    capacity_df = build_wide_table(core_df)

    print("Adding completeness flags...")
    capacity_df = add_completeness_flags(capacity_df)

    print("Calculating teacher metrics...")
    capacity_df = add_teacher_metrics(capacity_df)

    print("Calculating classroom metrics...")
    capacity_df = add_classroom_metrics(capacity_df)

    print("Adding warning flags...")
    capacity_df = add_priority_flags(capacity_df)

    # Save complete and incomplete rows so source gaps remain visible.
    capacity_df.to_parquet(OUTPUT_PATH, index=False)

    print(f"Saved analytical table to: {OUTPUT_PATH}")
    print(f"Rows: {len(capacity_df):,}")
    print(f"Complete rows: {capacity_df['is_complete'].sum():,}")
    print(f"Incomplete rows: {(~capacity_df['is_complete']).sum():,}")

    print("\nTeacher warnings:")
    print(capacity_df["teacher_warning"].value_counts(dropna=False))

    print("\nClassroom warnings:")
    print(capacity_df["classroom_warning"].value_counts(dropna=False))

    print("\nTeacher ratio mismatches:")
    print(capacity_df["teacher_ratio_mismatch"].value_counts(dropna=False))

    print("\nExtreme teacher ratios:")
    print(capacity_df["extreme_teacher_ratio"].value_counts(dropna=False))

    print("\nExtreme classroom ratios:")
    print(capacity_df["extreme_classroom_ratio"].value_counts(dropna=False))

if __name__ == "__main__":
    main()