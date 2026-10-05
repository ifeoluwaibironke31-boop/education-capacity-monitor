from pathlib import Path
import geopandas as gpd

# Find the project root automatically.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Define input and output locations.
REFERENCE_DIR = PROJECT_ROOT / "data" / "reference"
STATE_PATH = REFERENCE_DIR / "nigeria_states.geojson"
LGA_PATH = REFERENCE_DIR / "nigeria_lgas.geojson"
OUTPUT_PATH = REFERENCE_DIR / "nigeria_lgas_enriched.geojson"

def load_boundaries():
    """Load Nigeria state and LGA boundary files."""
    states = gpd.read_file(STATE_PATH)
    lgas = gpd.read_file(LGA_PATH)

    return states, lgas

def prepare_states(states):
    """Prepare state polygons for spatial matching."""
    states = states[
        [
            "shapeID",
            "shapeName",
            "geometry",
        ]
    ].copy()

    states = states.rename(
        columns={
            "shapeID": "state_shape_id",
            "shapeName": "state",
        }
    )

    return states

def prepare_lgas(lgas):
    """Prepare LGA polygons while preserving their unique GeoJSON IDs."""
    lgas = lgas[
        [
            "shapeID",
            "shapeName",
            "geometry",
        ]
    ].copy()

    lgas = lgas.rename(
        columns={
            "shapeID": "lga_shape_id",
            "shapeName": "lga",
        }
    )

    return lgas

def attach_states(lgas, states):
    """Determine which state contains each LGA using spatial matching."""

    # Work with representative points so each LGA is matched to the
    # state polygon containing an interior point of that LGA.
    lga_points = lgas[
        [
            "lga_shape_id",
            "lga",
            "geometry",
        ]
    ].copy()

    lga_points["geometry"] = (
        lga_points.geometry
        .representative_point()
    )

    # Match each LGA representative point to its containing state.
    matched = gpd.sjoin(
        lga_points,
        states[
            [
                "state_shape_id",
                "state",
                "geometry",
            ]
        ],
        how="left",
        predicate="within",
    )

    # Keep one state assignment for each unique LGA polygon.
    lookup = matched[
        [
            "lga_shape_id",
            "state_shape_id",
            "state",
        ]
    ].drop_duplicates(
        subset=["lga_shape_id"]
    )

    # Attach the state information back to the original LGA polygons.
    enriched = lgas.merge(
        lookup,
        on="lga_shape_id",
        how="left",
        validate="one_to_one",
    )

    return enriched

def validate_output(enriched):
    """Run basic checks on the enriched geographic reference."""
    print("\nValidation:")

    print(
        "Total LGAs:",
        len(enriched),
    )

    print(
        "Unique LGA polygons:",
        enriched["lga_shape_id"].nunique(),
    )

    print(
        "Missing state assignments:",
        enriched["state"].isna().sum(),
    )

    print(
        "States represented:",
        enriched["state"].nunique(),
    )

    duplicate_ids = (
        enriched["lga_shape_id"]
        .duplicated()
        .sum()
    )

    print(
        "Duplicate LGA shape IDs:",
        duplicate_ids,
    )

def main():
    """Build the enriched Nigeria LGA geographic reference file."""
    print("Loading boundary files...")

    states, lgas = load_boundaries()

    print(
        f"State boundaries: {len(states):,}"
    )

    print(
        f"LGA boundaries: {len(lgas):,}"
    )

    print("Preparing boundaries...")

    states = prepare_states(states)
    lgas = prepare_lgas(lgas)

    print("Matching LGAs to states...")

    enriched = attach_states(
        lgas,
        states,
    )

    validate_output(enriched)

    print("\nSample:")
    print(
        enriched[
            [
                "state",
                "lga",
            ]
        ]
        .head(20)
        .to_string(index=False)
    )

    enriched.to_file(
        OUTPUT_PATH,
        driver="GeoJSON",
    )

    print(
        f"\nSaved enriched boundaries to: {OUTPUT_PATH}"
    )

if __name__ == "__main__":
    main()