from pathlib import Path
from difflib import get_close_matches
import re
import geopandas as gpd
import pandas as pd

# Find the project root automatically.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

GEO_PATH = (
    PROJECT_ROOT
    / "data"
    / "reference"
    / "nigeria_lgas_enriched.geojson"
)

CAPACITY_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "dnemis"
    / "2024_2025"
    / "education_capacity_wide.parquet"
)

# Known state-name differences between GeoJSON and DNEMIS.
STATE_ALIASES = {
    "akwa ibom": "akwa ibom",
    "akwa-ibom": "akwa ibom",
    "anambra state": "anambra",
    "anambra": "anambra",
    "abuja federal capital territory": "federal capital territory",
    "federal capital territory": "federal capital territory",
}

def normalize_name(value):
    """Normalize punctuation, spacing, and case for comparison."""
    if pd.isna(value):
        return value

    value = str(value).strip().lower()
    value = re.sub(r"[-/]", " ", value)
    value = re.sub(r"[.'’]", "", value)
    value = re.sub(r"\s+", " ", value).strip()

    return value

def normalize_state(value):
    """Normalize known differences in state names."""
    normalized = normalize_name(value)
    return STATE_ALIASES.get(normalized, normalized)

def main():
    """Diagnose unmatched GeoJSON LGAs without guessing replacements."""
    print("Loading geographic reference...")
    geo = gpd.read_file(GEO_PATH)

    print("Loading DNEMIS capacity data...")
    capacity = pd.read_parquet(CAPACITY_PATH)

    geo_names = (
        geo[["state", "lga"]]
        .drop_duplicates()
        .copy()
    )

    dnemis_names = (
        capacity[["state", "lga"]]
        .drop_duplicates()
        .copy()
    )

    # Create normalized keys.
    geo_names["state_key"] = geo_names["state"].apply(normalize_state)
    geo_names["lga_key"] = geo_names["lga"].apply(normalize_name)

    dnemis_names["state_key"] = dnemis_names["state"].apply(normalize_state)
    dnemis_names["lga_key"] = dnemis_names["lga"].apply(normalize_name)

    # Find exact matches first.
    dnemis_keys = set(
        zip(
            dnemis_names["state_key"],
            dnemis_names["lga_key"],
        )
    )

    unmatched = geo_names[
        ~geo_names.apply(
            lambda row: (
                row["state_key"],
                row["lga_key"],
            ) in dnemis_keys,
            axis=1,
        )
    ].copy()

    results = []

    for _, row in unmatched.iterrows():
        state_key = row["state_key"]
        lga_key = row["lga_key"]

        # Look only at DNEMIS LGAs within the same state.
        state_candidates = dnemis_names[
            dnemis_names["state_key"] == state_key
        ].copy()

        # If the state has no DNEMIS records at all, this is a coverage gap.
        if state_candidates.empty:
            results.append(
                {
                    "geo_state": row["state"],
                    "geo_lga": row["lga"],
                    "status": "STATE MISSING FROM DNEMIS",
                    "candidate_1": "",
                    "candidate_2": "",
                    "candidate_3": "",
                }
            )
            continue

        candidate_keys = state_candidates[
            "lga_key"
        ].dropna().unique().tolist()

        # Find similar LGA spellings within the same state.
        matches = get_close_matches(
            lga_key,
            candidate_keys,
            n=3,
            cutoff=0.55,
        )

        candidate_names = []

        for match in matches:
            original = state_candidates[
                state_candidates["lga_key"] == match
            ]["lga"].iloc[0]

            candidate_names.append(original)

        while len(candidate_names) < 3:
            candidate_names.append("")

        results.append(
            {
                "geo_state": row["state"],
                "geo_lga": row["lga"],
                "status": (
                    "POSSIBLE NAME DIFFERENCE"
                    if matches
                    else "NO CLOSE DNEMIS MATCH"
                ),
                "candidate_1": candidate_names[0],
                "candidate_2": candidate_names[1],
                "candidate_3": candidate_names[2],
            }
        )

    result_df = pd.DataFrame(results)

    print("\nDIAGNOSTIC SUMMARY")
    print("------------------")
    print(result_df["status"].value_counts().to_string())

    print("\nUNMATCHED DIAGNOSTICS")
    print("---------------------")

    print(
        result_df
        .sort_values(
            [
                "geo_state",
                "geo_lga",
            ]
        )
        .to_string(index=False)
    )

if __name__ == "__main__":
    main()