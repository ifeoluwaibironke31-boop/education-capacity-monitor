from pathlib import Path
import re
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "dnemis" / "2024_2025"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "dnemis" / "2024_2025"
OUTPUT_PATH = PROCESSED_DIR / "reporting_metrics.parquet"

ACTUAL_INDICATORS = {
    "MD: ANFE (IQS/IQTE) actual reports",
    "MD: JSS actual reports",
    "MD: Pre&Primary actual reports",
    "MD: Private schools - Actual Reports",
    "MD: SSS actual reports",
    "MD: Sci/Tech/ Voc actual reports",
}

EXPECTED_INDICATORS = {
    "MD: ANFE (IQS/IQTE) expected reports",
    "MD: JSS expected reports",
    "MD: Pre&Primary expected reports",
    "MD: Private schools - Expected Reports",
    "MD: SSS expected reports",
    "MD: Sci/Tech/ Voc expected reports",
}

TOTAL_SCHOOLS_INDICATOR = "MD: Total schools"


def clean_geo_name(value):
    if pd.isna(value):
        return None
    return re.sub(r"^[A-Za-z]{2}\s+", "", str(value).strip()).strip()


def clean_state_name(value):
    value = clean_geo_name(value)
    if not value:
        return None
    return re.sub(r"\s+State$", "", value, flags=re.IGNORECASE).strip()


def clean_lga_name(value):
    value = clean_geo_name(value)
    if not value:
        return None
    return re.sub(r"\s+LGA$", "", value, flags=re.IGNORECASE).strip()


def classify_confidence(rate, valid):
    """Classify confidence only when the reporting ratio is logically valid."""
    if not valid:
        return "Check Source"
    if pd.isna(rate) or rate <= 0:
        return "No Data"
    if rate >= 80:
        return "High"
    if rate >= 50:
        return "Medium"
    return "Low"


def main():
    fact = pd.read_parquet(RAW_DIR / "fact.parquet")
    dx = pd.read_parquet(RAW_DIR / "dx.parquet").rename(
        columns={"id": "dx", "name": "indicator"}
    )
    ou = pd.read_parquet(RAW_DIR / "ou.parquet")

    fact = fact.merge(dx, on="dx", how="left")
    fact = fact[fact["periodType"].eq("YEARLY")].copy()

    relevant = fact[
        fact["indicator"].isin(
            ACTUAL_INDICATORS
            | EXPECTED_INDICATORS
            | {TOTAL_SCHOOLS_INDICATOR}
        )
    ].copy()

    relevant["metric"] = relevant["indicator"].map(
        lambda x: (
            "schools_reported"
            if x in ACTUAL_INDICATORS
            else "schools_expected"
            if x in EXPECTED_INDICATORS
            else "source_total_schools"
        )
    )

    metrics = (
        relevant.groupby(["pe", "ou", "metric"])["value"]
        .sum(min_count=1)
        .unstack("metric")
        .reset_index()
    )

    # Retain every Nigeria/state/LGA geography, even where reporting is absent.
    geography = ou[
        ou["level"].isin([1, 2, 3])
    ][["id", "name", "level", "parent_name"]].copy()

    years = pd.DataFrame({"pe": sorted(fact["pe"].dropna().unique())})
    geography["_key"] = 1
    years["_key"] = 1

    output = (
        geography.merge(years, on="_key")
        .drop(columns="_key")
        .rename(columns={"id": "ou"})
        .merge(metrics, on=["pe", "ou"], how="left")
    )

    output["year"] = output["pe"].astype(int)
    output["geo_level"] = output["level"].astype(int)

    output["state"] = output.apply(
        lambda row: (
            clean_state_name(row["name"])
            if row["geo_level"] == 2
            else clean_state_name(row["parent_name"])
            if row["geo_level"] == 3
            else None
        ),
        axis=1,
    )

    output["lga"] = output.apply(
        lambda row: clean_lga_name(row["name"])
        if row["geo_level"] == 3
        else None,
        axis=1,
    )

    output["geo_name"] = output.apply(
        lambda row: (
            "Nigeria"
            if row["geo_level"] == 1
            else row["state"]
            if row["geo_level"] == 2
            else row["lga"]
        ),
        axis=1,
    )

    output["reporting_rate"] = (
        output["schools_reported"]
        / output["schools_expected"].replace(0, pd.NA)
        * 100
    ).round(1)

    # A valid reporting rate requires a positive denominator and reported <= expected.
    output["reporting_valid"] = (
        output["schools_reported"].notna()
        & output["schools_expected"].notna()
        & output["schools_expected"].gt(0)
        & output["schools_reported"].ge(0)
        & output["schools_reported"].le(output["schools_expected"])
    )

    output["data_confidence"] = output.apply(
        lambda row: classify_confidence(
            row["reporting_rate"],
            row["reporting_valid"],
        ),
        axis=1,
    )

    output = output[
        [
            "year",
            "geo_level",
            "state",
            "lga",
            "geo_name",
            "ou",
            "schools_reported",
            "schools_expected",
            "reporting_rate",
            "data_confidence",
            "source_total_schools",
            "reporting_valid",
        ]
    ].sort_values(
        ["geo_level", "state", "lga"],
        na_position="first",
    ).reset_index(drop=True)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    output.to_parquet(OUTPUT_PATH, index=False)

    invalid = output[~output["reporting_valid"]]
    zero_reporting = output[
        output["reporting_valid"]
        & output["reporting_rate"].eq(0)
    ]

    print("Reporting metrics built successfully.")
    print(f"Rows: {len(output):,}")
    print(f"Valid reporting rows: {int(output['reporting_valid'].sum()):,}")
    print(f"Invalid reporting rows: {len(invalid):,}")
    print(f"Zero-reporting rows: {len(zero_reporting):,}")

    print("\nConfidence distribution:")
    print(output["data_confidence"].value_counts(dropna=False).to_string())

    if not invalid.empty:
        print("\nInvalid source reporting rows:")
        print(
            invalid[
                [
                    "state",
                    "lga",
                    "schools_reported",
                    "schools_expected",
                    "reporting_rate",
                ]
            ].to_string(index=False)
        )

    national = output[output["geo_level"] == 1].iloc[0]

    print("\nNational reporting summary:")
    print(f"Schools reported: {national['schools_reported']:,.0f}")
    print(f"Schools expected: {national['schools_expected']:,.0f}")
    print(f"Reporting rate: {national['reporting_rate']:.1f}%")
    print(f"Data confidence: {national['data_confidence']}")
    print(f"\nSaved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()