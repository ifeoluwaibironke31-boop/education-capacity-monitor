from pathlib import Path
import re
import geopandas as gpd
import pandas as pd

# Find the project root automatically.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Input files.
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

# Verified LGA naming differences between GeoJSON and DNEMIS.
# Only high-confidence equivalents are included here.
LGA_ALIASES = {
    ("abia", "umu nneochi"): "umunneochi",
    (
        "federal capital territory",
        "municipal area council",
    ): "abuja municipal area council",
    ("bayelsa", "yenegoa"): "yenagoa",
    ("benue", "oturkpo"): "otukpo",
    ("edo", "iguegben"): "igueben",
    ("ekiti", "gbonyin"): "aiyekire (gbonyin)",
    ("gombe", "shomgom"): "shongom",
    ("imo", "ezinihitte"): "ezinihitte mbaise",
    ("imo", "mbatoli"): "mbaitoli",
    ("jigawa", "biriniwa"): "birniwa",
    ("jigawa", "kiri kasama"): "kiri kasamma",
    ("kano", "garun malam"): "garun mallam",
    ("kano", "nassarawa"): "nasarawa",
    ("kebbi", "bagudu"): "bagudo",
    ("ogun", "shagamu"): "sagamu",
    ("osun", "atakunmosa east"): "atakumosa east",
    ("osun", "atakunmosa west"): "atakumosa west",
    ("osun", "ayedade"): "ayedaade",
    ("osun", "ilesha east"): "ilesa east",
    ("osun", "ilesha west"): "ilesa west",
    ("sokoto", "wamakko"): "wamako",
    ("yobe", "bursari"): "busari",
    ("zamfara", "birnin magaji kiyaw"): "birnin magaji",
}

def normalize_name(value):
    """Normalize punctuation, spacing, and case for comparison."""
    if pd.isna(value):
        return value

    value = str(value).strip().lower()

    # Treat hyphens and slashes as spaces.
    value = re.sub(r"[-/]", " ", value)

    # Remove punctuation that should not affect matching.
    value = re.sub(r"[.'’]", "", value)

    # Collapse repeated whitespace.
    value = re.sub(r"\s+", " ", value).strip()

    return value

def normalize_state(value):
    """Normalize known state naming differences."""
    normalized = normalize_name(value)

    return STATE_ALIASES.get(
        normalized,
        normalized,
    )

def normalize_lga(state_value, lga_value):
    """Normalize an LGA name and apply verified aliases."""
    state_key = normalize_state(state_value)
    lga_key = normalize_name(lga_value)

    return LGA_ALIASES.get(
        (state_key, lga_key),
        lga_key,
    )

def main():
    """Compare GeoJSON geography names with DNEMIS names."""
    print("Loading geographic reference...")
    geo = gpd.read_file(GEO_PATH)

    print("Loading capacity data...")
    capacity = pd.read_parquet(CAPACITY_PATH)

    # Keep unique state/LGA combinations from the geographic reference.
    geo_names = (
        geo[
            [
                "state",
                "lga",
            ]
        ]
        .drop_duplicates()
        .copy()
    )

    # Keep unique state/LGA combinations from DNEMIS.
    dnemis_names = (
        capacity[
            [
                "state",
                "lga",
            ]
        ]
        .drop_duplicates()
        .copy()
    )

    # Create normalized state keys.
    geo_names["state_key"] = (
        geo_names["state"]
        .apply(normalize_state)
    )

    dnemis_names["state_key"] = (
        dnemis_names["state"]
        .apply(normalize_state)
    )

    # Create normalized LGA keys using verified aliases.
    geo_names["lga_key"] = geo_names.apply(
        lambda row: normalize_lga(
            row["state"],
            row["lga"],
        ),
        axis=1,
    )

    dnemis_names["lga_key"] = dnemis_names.apply(
        lambda row: normalize_lga(
            row["state"],
            row["lga"],
        ),
        axis=1,
    )

    # Match GeoJSON LGAs to DNEMIS LGAs.
    comparison = geo_names.merge(
        dnemis_names[
            [
                "state_key",
                "lga_key",
                "state",
                "lga",
            ]
        ],
        on=[
            "state_key",
            "lga_key",
        ],
        how="left",
        suffixes=(
            "_geo",
            "_dnemis",
        ),
    )

    matched = (
        comparison["lga_dnemis"]
        .notna()
        .sum()
    )

    unmatched = (
        comparison["lga_dnemis"]
        .isna()
        .sum()
    )

    print("\nMATCH SUMMARY")
    print("-------------")
    print(
        f"GeoJSON LGAs: {len(geo_names):,}"
    )
    print(
        f"DNEMIS LGAs: {len(dnemis_names):,}"
    )
    print(
        f"Matched: {matched:,}"
    )
    print(
        f"Unmatched: {unmatched:,}"
    )

    print("\nUNMATCHED GEOJSON LGAs")
    print("----------------------")

    unmatched_rows = comparison[
        comparison["lga_dnemis"].isna()
    ][
        [
            "state_geo",
            "lga_geo",
        ]
    ]

    print(
        unmatched_rows
        .sort_values(
            [
                "state_geo",
                "lga_geo",
            ]
        )
        .to_string(index=False)
    )

if __name__ == "__main__":
    main()