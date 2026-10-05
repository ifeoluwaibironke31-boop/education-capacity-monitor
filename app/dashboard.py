import json
import os
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine

# ---------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------

st.set_page_config(
    page_title="Nigeria Education Capacity Monitor",
    page_icon="🗺️",
    layout="wide",
)

# ---------------------------------------------------------
# PROJECT PATHS
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

STATE_GEOJSON_PATH = (
    PROJECT_ROOT
    / "data"
    / "reference"
    / "nigeria_states.geojson"
)

LGA_GEOJSON_PATH = (
    PROJECT_ROOT
    / "data"
    / "reference"
    / "nigeria_lgas_enriched.geojson"
)

# ---------------------------------------------------------
# DATABASE SETTINGS
# ---------------------------------------------------------

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "education_capacity")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# ---------------------------------------------------------
# COLOR SCALE
# ---------------------------------------------------------

RISK_COLORS = [
    [0.00, "#2E8B57"],
    [0.25, "#B7C96F"],
    [0.50, "#F2C94C"],
    [0.75, "#F2994A"],
    [1.00, "#C62828"],
]

# ---------------------------------------------------------
# NAME NORMALIZATION
# ---------------------------------------------------------

STATE_ALIASES = {
    "akwa ibom": "akwa ibom",
    "akwa-ibom": "akwa ibom",
    "anambra": "anambra",
    "anambra state": "anambra",
    "abuja federal capital territory": "federal capital territory",
    "federal capital territory": "federal capital territory",
}

def normalize_name(value):
    """Normalize names for matching across different data sources."""
    if pd.isna(value):
        return value

    value = str(value).strip().lower()
    value = re.sub(r"[-/]", " ", value)
    value = re.sub(r"[.'’]", "", value)
    value = re.sub(r"\s+", " ", value).strip()

    return value

def normalize_state(value):
    """Normalize known state-name differences."""
    normalized = normalize_name(value)

    return STATE_ALIASES.get(
        normalized,
        normalized,
    )

# ---------------------------------------------------------
# DATABASE CONNECTION
# ---------------------------------------------------------

@st.cache_resource
def create_db_engine():
    """Create and cache the PostgreSQL connection."""
    if not DB_PASSWORD:
        st.error(
            "DB_PASSWORD is not set. "
            "Set it in PowerShell before starting Streamlit."
        )
        st.stop()

    connection_url = (
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    return create_engine(connection_url)

@st.cache_data
def load_capacity_data():
    """Load complete analytical records from PostgreSQL."""
    engine = create_db_engine()

    query = """
        SELECT *
        FROM capacity_metrics
        WHERE is_complete = TRUE
    """

    return pd.read_sql(
        query,
        engine,
    )

# ---------------------------------------------------------
# GEOJSON LOADERS
# ---------------------------------------------------------

@st.cache_data
def load_state_geojson():
    """Load Nigeria state boundaries."""
    with open(
        STATE_GEOJSON_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)

@st.cache_data
def load_lga_reference():
    """Load the enriched LGA geographic reference."""
    with open(
        LGA_GEOJSON_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    rows = []

    for feature in data["features"]:
        props = feature["properties"]

        rows.append(
            {
                "state": props["state"],
                "lga": props["lga"],
            }
        )

    return pd.DataFrame(rows)

# ---------------------------------------------------------
# PRESSURE / SEVERITY HELPERS
# ---------------------------------------------------------

def classify_pressure(value):
    """Convert pressure index into a readable severity label."""
    if pd.isna(value):
        return "No Data"

    if value <= 1:
        return "Normal"

    if value <= 1.5:
        return "Moderate"

    if value <= 2:
        return "High"

    if value <= 3:
        return "Severe"

    return "Critical"

# ---------------------------------------------------------
# STATE-LEVEL AGGREGATION
# ---------------------------------------------------------

def build_state_summary(capacity_df, lga_reference):
    """Aggregate complete records into state-level pressure measures."""
    df = capacity_df.copy()
    ref = lga_reference.copy()

    df["state_key"] = (
        df["state"]
        .apply(normalize_state)
    )

    ref["state_key"] = (
        ref["state"]
        .apply(normalize_state)
    )

    total_lgas = (
        ref
        .groupby("state_key")["lga"]
        .nunique()
        .rename("total_lgas")
    )

    analysed_lgas = (
        df
        .groupby("state_key")["lga"]
        .nunique()
        .rename("analysed_lgas")
    )

    # Use the 75th percentile so one extreme record
    # does not define the whole state's pressure.
    state_metrics = (
        df
        .groupby("state_key")
        .agg(
            teacher_pressure=(
                "teacher_pressure_index",
                lambda x: x.quantile(0.75),
            ),
            classroom_pressure=(
                "classroom_pressure_index",
                lambda x: x.quantile(0.75),
            ),
            teacher_warnings=(
                "teacher_warning",
                "sum",
            ),
            classroom_warnings=(
                "classroom_warning",
                "sum",
            ),
            record_count=(
                "lga",
                "size",
            ),
        )
    )

    summary = (
        pd.concat(
            [
                state_metrics,
                total_lgas,
                analysed_lgas,
            ],
            axis=1,
        )
        .reset_index()
    )

    summary["analysed_lgas"] = (
        summary["analysed_lgas"]
        .fillna(0)
        .astype(int)
    )

    summary["total_lgas"] = (
        summary["total_lgas"]
        .fillna(0)
        .astype(int)
    )

    summary["coverage_pct"] = (
        summary["analysed_lgas"]
        / summary["total_lgas"].replace(0, pd.NA)
        * 100
    )

    summary["overall_pressure"] = summary[
        [
            "teacher_pressure",
            "classroom_pressure",
        ]
    ].max(axis=1)

    summary["severity"] = (
        summary["overall_pressure"]
        .apply(classify_pressure)
    )

    return summary

# ---------------------------------------------------------
# MAP DATAFRAME
# ---------------------------------------------------------

def build_map_dataframe(state_geojson, state_summary):
    """Create one row per state polygon and attach analytical metrics."""
    rows = []

    for feature in state_geojson["features"]:
        props = feature["properties"]

        state_name = props["shapeName"]

        rows.append(
            {
                "state_name": state_name,
                "state_key": normalize_state(state_name),
            }
        )

    map_df = pd.DataFrame(rows)

    map_df = map_df.merge(
        state_summary,
        on="state_key",
        how="left",
    )

    map_df["has_data"] = (
        map_df["record_count"]
        .notna()
    )

    map_df["coverage_pct"] = (
        map_df["coverage_pct"]
        .fillna(0)
    )

    return map_df

# ---------------------------------------------------------
# MAP CREATION
# ---------------------------------------------------------

def create_state_map(
    map_df,
    state_geojson,
    risk_column,
    risk_label,
):
    """Create Nigeria state map on a dark basemap."""
    display_df = map_df.copy()

    display_df["severity"] = (
        display_df[risk_column]
        .apply(classify_pressure)
    )

    fig = px.choropleth_map(
        display_df,
        geojson=state_geojson,
        locations="state_name",
        featureidkey="properties.shapeName",
        color=risk_column,
        hover_name="state_name",
        hover_data={
            risk_column: ":.2f",
            "severity": True,
            "coverage_pct": ":.0f",
            "analysed_lgas": True,
            "total_lgas": True,
            "state_name": False,
        },
        color_continuous_scale=RISK_COLORS,
        range_color=(0, 3),
        map_style="carto-darkmatter",
        center={
            "lat": 9.0820,
            "lon": 8.6753,
        },
        zoom=4.7,
        opacity=0.82,
        height=650,
        labels={
            risk_column: risk_label,
            "severity": "Severity",
            "coverage_pct": "Data coverage %",
            "analysed_lgas": "LGAs with data",
            "total_lgas": "Official LGAs",
        },
    )

    fig.update_traces(
        marker_line_width=1.2,
        marker_line_color="#222222",
    )

    fig.update_layout(
        margin=dict(
            l=0,
            r=0,
            t=0,
            b=0,
        ),
        coloraxis_colorbar=dict(
            title=risk_label,
            thickness=18,
            len=0.7,
        ),
    )

    return fig

# ---------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------

capacity_df = load_capacity_data()
state_geojson = load_state_geojson()
lga_reference = load_lga_reference()

state_summary = build_state_summary(
    capacity_df,
    lga_reference,
)

map_df = build_map_dataframe(
    state_geojson,
    state_summary,
)

# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------

st.title("Nigeria Education Capacity Monitor")

st.caption(
    "Explore teacher distribution pressure and classroom overcrowding "
    "across Nigeria using DNEMIS education data."
)

# ---------------------------------------------------------
# KPI CARDS
# ---------------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Analyzable Records",
    f"{len(capacity_df):,}",
)

col2.metric(
    "Teacher Warnings",
    f"{int(capacity_df['teacher_warning'].sum()):,}",
)

col3.metric(
    "Classroom Warnings",
    f"{int(capacity_df['classroom_warning'].sum()):,}",
)

critical_cases = (
    capacity_df["teacher_warning"]
    & capacity_df["classroom_warning"]
).sum()

col4.metric(
    "Dual Capacity Warnings",
    f"{int(critical_cases):,}",
)

# ---------------------------------------------------------
# RISK VIEW
# ---------------------------------------------------------

st.subheader("Risk View")

risk_mode = st.segmented_control(
    "Choose the capacity problem shown on the map",
    options=[
        "Overall Capacity Risk",
        "Teacher Pressure",
        "Classroom Overcrowding",
    ],
    default="Overall Capacity Risk",
)

if risk_mode == "Teacher Pressure":
    risk_column = "teacher_pressure"
    risk_label = "Teacher Pressure"

elif risk_mode == "Classroom Overcrowding":
    risk_column = "classroom_pressure"
    risk_label = "Classroom Pressure"

else:
    risk_column = "overall_pressure"
    risk_label = "Overall Capacity Risk"

# ---------------------------------------------------------
# NIGERIA MAP
# ---------------------------------------------------------

st.subheader("Nigeria")

st.write(
    "State colors show education-capacity pressure. "
    "Hover over a state to view its risk and data coverage."
)

fig = create_state_map(
    map_df,
    state_geojson,
    risk_column,
    risk_label,
)

st.plotly_chart(
    fig,
    width="stretch",
)

st.caption(
    "Green = lower pressure · "
    "Yellow = moderate pressure · "
    "Orange = high pressure · "
    "Red = severe pressure"
)

# ---------------------------------------------------------
# NO-DATA NOTICE
# ---------------------------------------------------------

missing_states = (
    map_df[
        ~map_df["has_data"]
    ]["state_name"]
    .tolist()
)

if missing_states:
    st.info(
        "No complete DNEMIS capacity data is available for: "
        + ", ".join(missing_states)
    )

# ---------------------------------------------------------
# STATE SUMMARY TABLE
# ---------------------------------------------------------

with st.expander(
    "View state-level summary table"
):
    summary_table = map_df[
        [
            "state_name",
            "overall_pressure",
            "teacher_pressure",
            "classroom_pressure",
            "severity",
            "coverage_pct",
            "analysed_lgas",
            "total_lgas",
        ]
    ].copy()

    summary_table = summary_table.rename(
        columns={
            "state_name": "State",
            "overall_pressure": "Overall Risk",
            "teacher_pressure": "Teacher Pressure",
            "classroom_pressure": "Classroom Pressure",
            "severity": "Severity",
            "coverage_pct": "Coverage %",
            "analysed_lgas": "LGAs with Data",
            "total_lgas": "Official LGAs",
        }
    )

    summary_table = summary_table.sort_values(
        "Overall Risk",
        ascending=False,
        na_position="last",
    )

    st.dataframe(
        summary_table,
        width="stretch",
        hide_index=True,
    )