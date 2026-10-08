import copy
import os
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import create_engine

st.set_page_config(
    page_title="Nigerian Education Capacity Monitor",
    page_icon="🇳🇬",
    layout="wide",
    initial_sidebar_state="expanded",
)

MAP_CONFIG = {
    "scrollZoom": False,
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": ["toImage", "resetViewMap"],
}

# =========================================================
# STYLE
# =========================================================

st.markdown(
    """
<style>
:root{--background:#070d16;--sidebar:#09111d;--surface:#0f1826;--border:#223047;--text:#f3f6fb}
html,body,[data-testid="stAppViewContainer"],.stApp{background:var(--background);color:var(--text)}
[data-testid="stHeader"]{background:#070d16;border-bottom:1px solid #172232}
[data-testid="stToolbar"]{color:#dbe5f3}
.block-container{max-width:1500px;padding:4.2rem 2.3rem 2rem!important}
section[data-testid="stSidebar"],section[data-testid="stSidebar"]>div{background:var(--sidebar)}
section[data-testid="stSidebar"]{border-right:1px solid var(--border)}
[data-testid="stSidebar"] *{color:#e7edf7}
[data-testid="stSidebar"] hr{border-color:#243349}
.sidebar-brand{padding:22px 4px 18px}
.sidebar-brand-title{font-size:1.35rem;line-height:1.3;font-weight:800;color:#fff;margin-bottom:10px;max-width:290px}
.sidebar-brand-subtitle{color:#8a98ad;font-size:.82rem;line-height:1.55;max-width:300px}
.sidebar-section{color:#6f8098;text-transform:uppercase;letter-spacing:.1em;font-weight:800;font-size:.68rem;margin:21px 0 9px}
section[data-testid="stSidebar"] .stButton button{width:100%;min-height:42px;border-radius:9px;background:#101a2a;border:1px solid #25354b;color:#e7edf7;font-weight:600;text-align:left;justify-content:flex-start;padding-left:14px}
section[data-testid="stSidebar"] .stButton button:hover{background:#162238;border-color:#3a506f;color:#fff}
section[data-testid="stSidebar"] .stButton button p{color:inherit!important}
section[data-testid="stSidebar"] [data-testid="stCheckbox"]{margin:-5px 0}
section[data-testid="stSidebar"] [data-testid="stCheckbox"] label{padding:1px 0}
section[data-testid="stSidebar"] [data-testid="stCheckbox"] p{color:#e0e7f1!important;font-size:.9rem;font-weight:500}
section[data-testid="stSidebar"] [data-baseweb="select"]>div{background:#101a2a;border-color:#25354b}
h1,h2,h3,h4{color:#f5f7fb!important}
p{color:#a6b1c2}
.dashboard-title{color:#f5f7fb;font-size:2rem;font-weight:800;line-height:1.25;margin:0 0 6px}
.dashboard-subtitle{color:#8391a6;font-size:.97rem;margin-bottom:24px}
.section-label{color:#7788a0;text-transform:uppercase;letter-spacing:.09em;font-size:.72rem;font-weight:800;margin:21px 0 7px}
[data-testid="stMetric"]{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:16px 18px;box-shadow:0 8px 22px rgba(0,0,0,.15)}
[data-testid="stMetricLabel"],[data-testid="stMetricLabel"] p{color:#8594aa!important;font-weight:600}
[data-testid="stMetricValue"]{color:#f1f5fb;font-weight:800}
[data-testid="stPlotlyChart"]{background:transparent!important;border:none!important;border-radius:0!important;overflow:visible!important;box-shadow:none!important;padding:0!important}
.modebar{background:rgba(9,17,29,.88)!important;border-radius:9px!important;padding:3px!important}
.modebar-btn path{fill:#dce5f2!important}
.modebar-btn:hover path{fill:#fff!important}
[data-testid="stExpander"]{background:var(--surface);border:1px solid var(--border);border-radius:12px}
[data-testid="stExpander"] summary{color:#d8e0ec}
.info-card{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:18px 20px;color:#cfd8e6;margin-bottom:15px}
.info-card strong{color:#fff}
.badge-row{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin:5px 0 12px}
.dashboard-badge{color:#fff;border-radius:999px;padding:7px 14px;font-size:.82rem;font-weight:750;display:inline-block}
.sidebar-risk-row{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:8px 2px;border-bottom:1px solid #1d2a3d;color:#cdd7e5;font-size:.82rem}
.sidebar-risk-score{color:#fff;font-weight:750}
.table-shell{width:100%;overflow-x:auto;margin-top:6px}
.blend-table{width:100%;border-collapse:collapse;color:#dbe4f2;font-size:.76rem;line-height:1.35}
.blend-table thead th{color:#94a4bc;font-weight:700;text-align:left;padding:9px 10px;border-bottom:1px solid #263348;white-space:nowrap}
.blend-table tbody td{padding:9px 10px;border-bottom:1px solid #192536;white-space:nowrap}
.blend-table tbody tr:hover td{background:rgba(255,255,255,.03)}
[data-testid="stCaptionContainer"] p{color:#78869a!important}
footer{background:var(--background)}
</style>
""",
    unsafe_allow_html=True,
)

# =========================================================
# PATHS + CONFIGURATION
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_GEOJSON_PATH = PROJECT_ROOT / "data" / "reference" / "nigeria_states.geojson"
LGA_GEOJSON_PATH = PROJECT_ROOT / "data" / "reference" / "nigeria_lgas_enriched.geojson"

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "education_capacity")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")

RISK_COLORS = [
    [0.00, "#2E8B57"],
    [0.25, "#AFC75D"],
    [0.50, "#E4C43F"],
    [0.75, "#E77A35"],
    [1.00, "#C92B2B"],
]

STATE_ALIASES = {
    "akwa ibom": "akwa ibom",
    "akwa-ibom": "akwa ibom",
    "anambra": "anambra",
    "anambra state": "anambra",
    "abuja federal capital territory": "federal capital territory",
    "federal capital territory": "federal capital territory",
}

LGA_ALIASES = {
    ("abia", "umu nneochi"): "umunneochi",
    ("federal capital territory", "municipal area council"): "abuja municipal area council",
    ("bayelsa", "yenegoa"): "yenagoa",
    ("benue", "oturkpo"): "otukpo",
    ("edo", "iguegben"): "igueben",
    ("ekiti", "gbonyin"): "aiyekire (gbonyin)",
    ("gombe", "shomgom"): "shongom",
    ("imo", "ezinihitte"): "ezinihitte mbaise",
    ("imo", "mbatoli"): "mbaitoli",
    ("jigawa", "biriniwa"): "birniwa",
    ("jigawa", "kiri kasama"): "kiri kasamma",
    ("kano", "danbatta"): "dambatta",
    ("kano", "garun malam"): "garun mallam",
    ("kano", "garum mallam"): "garun mallam",
    ("kano", "nassarawa"): "nasarawa",
    ("kebbi", "bagudu"): "bagudo",
    ("kebbi", "arewa"): "arewa dandi",
    ("kebbi", "danko wasagu"): "wasagu danko",
    ("nasarawa", "nasarawa eggon"): "nasarawa egon",
    ("niger", "muya"): "munya",
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

# =========================================================
# GEOGRAPHY
# =========================================================

def normalize_name(value):
    if pd.isna(value):
        return value

    value = str(value).strip().lower()
    value = re.sub(r"[-/]", " ", value)
    value = re.sub(r"[.'’]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_state(value):
    normalized = normalize_name(value)
    return STATE_ALIASES.get(normalized, normalized)


def normalize_lga(state_value, lga_value):
    state_key = normalize_state(state_value)
    lga_key = normalize_name(lga_value)
    return LGA_ALIASES.get((state_key, lga_key), lga_key)

# =========================================================
# DATABASE + FILES
# =========================================================

@st.cache_resource
def create_db_engine():
    if not DB_PASSWORD:
        st.error("DB_PASSWORD is not set. Set it before starting Streamlit.")
        st.stop()

    url = (
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    return create_engine(url)


@st.cache_data
def load_capacity_data():
    query = """
        SELECT *
        FROM capacity_metrics
        WHERE is_complete = TRUE
    """
    return pd.read_sql(query, create_db_engine())


@st.cache_data
def load_state_geojson():
    with open(STATE_GEOJSON_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


@st.cache_data
def load_lga_geojson():
    with open(LGA_GEOJSON_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def build_lga_reference(lga_geojson):
    rows = []

    for feature in lga_geojson["features"]:
        props = feature["properties"]
        rows.append({"state": props["state"], "lga": props["lga"]})

    return pd.DataFrame(rows)

# =========================================================
# RISK + CONFIDENCE
# =========================================================

def classify_pressure(value):
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


def severity_color(severity):
    colors = {
        "Normal": "#2E8B57",
        "Moderate": "#B89D24",
        "High": "#D8772D",
        "Severe": "#D64541",
        "Critical": "#9E2020",
        "No Data": "#586577",
    }
    return colors.get(severity, "#586577")


def classify_data_confidence(coverage_pct):
    if pd.isna(coverage_pct) or coverage_pct <= 0:
        return "No Data"
    if coverage_pct >= 80:
        return "High"
    if coverage_pct >= 50:
        return "Medium"
    return "Low"


def confidence_color(confidence):
    colors = {
        "High": "#238A67",
        "Medium": "#B58D25",
        "Low": "#C96E2F",
        "No Data": "#586577",
    }
    return colors.get(confidence, "#586577")


def render_badges(severity, confidence=None):
    color = severity_color(severity)

    html = (
        '<div class="badge-row">'
        f'<span class="dashboard-badge" style="background:{color};">'
        f"{severity} Capacity Pressure</span>"
    )

    if confidence is not None:
        color = confidence_color(confidence)
        html += (
            f'<span class="dashboard-badge" style="background:{color};">'
            f"{confidence} Data Confidence</span>"
        )

    st.markdown(html + "</div>", unsafe_allow_html=True)

# =========================================================
# DATA PREPARATION
# =========================================================

def prepare_capacity_data(df):
    df = df.copy()
    df["state_key"] = df["state"].apply(normalize_state)
    df["lga_key"] = df.apply(
        lambda row: normalize_lga(row["state"], row["lga"]),
        axis=1,
    )
    return df


def build_state_summary(capacity_df, lga_reference):
    df = capacity_df.copy()
    ref = lga_reference.copy()

    ref["state_key"] = ref["state"].apply(normalize_state)
    ref["lga_key"] = ref.apply(
        lambda row: normalize_lga(row["state"], row["lga"]),
        axis=1,
    )

    official_lgas = ref[["state_key", "lga_key"]].drop_duplicates()
    data_lgas = df[["state_key", "lga_key"]].drop_duplicates()

    matched_lgas = official_lgas.merge(
        data_lgas,
        on=["state_key", "lga_key"],
        how="inner",
    )

    total_lgas = (
        official_lgas.groupby("state_key")["lga_key"]
        .nunique()
        .rename("total_lgas")
    )

    analysed_lgas = (
        matched_lgas.groupby("state_key")["lga_key"]
        .nunique()
        .rename("analysed_lgas")
    )

    state_metrics = df.groupby("state_key").agg(
        teacher_pressure=(
            "teacher_pressure_index",
            lambda x: x.quantile(0.75),
        ),
        classroom_pressure=(
            "classroom_pressure_index",
            lambda x: x.quantile(0.75),
        ),
        teacher_warnings=("teacher_warning", "sum"),
        classroom_warnings=("classroom_warning", "sum"),
        record_count=("lga", "size"),
    )

    summary = pd.concat(
        [state_metrics, total_lgas, analysed_lgas],
        axis=1,
    ).reset_index()

    summary["analysed_lgas"] = summary["analysed_lgas"].fillna(0).astype(int)
    summary["total_lgas"] = summary["total_lgas"].fillna(0).astype(int)

    summary["coverage_pct"] = (
        summary["analysed_lgas"]
        / summary["total_lgas"].replace(0, pd.NA)
        * 100
    ).fillna(0)

    summary["data_confidence"] = summary["coverage_pct"].apply(
        classify_data_confidence
    )

    summary["overall_pressure"] = summary[
        ["teacher_pressure", "classroom_pressure"]
    ].max(axis=1)

    return summary


def build_state_map_dataframe(state_geojson, state_summary):
    rows = []

    for feature in state_geojson["features"]:
        state_name = feature["properties"]["shapeName"]

        rows.append(
            {
                "state_name": state_name,
                "state_key": normalize_state(state_name),
            }
        )

    map_df = pd.DataFrame(rows).merge(
        state_summary,
        on="state_key",
        how="left",
    )

    map_df["coverage_pct"] = map_df["coverage_pct"].fillna(0)
    map_df["analysed_lgas"] = map_df["analysed_lgas"].fillna(0).astype(int)
    map_df["total_lgas"] = map_df["total_lgas"].fillna(0).astype(int)
    map_df["data_confidence"] = map_df["coverage_pct"].apply(
        classify_data_confidence
    )
    map_df["has_data"] = map_df["record_count"].notna()

    return map_df


def build_lga_summary(capacity_df, selected_state):
    state_key = normalize_state(selected_state)

    state_data = capacity_df[
        capacity_df["state_key"] == state_key
    ].copy()

    if state_data.empty:
        return pd.DataFrame()

    summary = (
        state_data.groupby("lga_key")
        .agg(
            dnemis_lga=("lga", "first"),
            teacher_pressure=(
                "teacher_pressure_index",
                lambda x: x.quantile(0.75),
            ),
            classroom_pressure=(
                "classroom_pressure_index",
                lambda x: x.quantile(0.75),
            ),
            teacher_warnings=("teacher_warning", "sum"),
            classroom_warnings=("classroom_warning", "sum"),
            record_count=("lga", "size"),
        )
        .reset_index()
    )

    summary["overall_pressure"] = summary[
        ["teacher_pressure", "classroom_pressure"]
    ].max(axis=1)

    return summary


def get_state_lga_geojson(lga_geojson, selected_state):
    selected_state_key = normalize_state(selected_state)
    features = []

    for feature in lga_geojson["features"]:
        props = feature["properties"]

        if normalize_state(props["state"]) == selected_state_key:
            features.append(copy.deepcopy(feature))

    return {"type": "FeatureCollection", "features": features}


def build_lga_map_dataframe(state_lga_geojson, lga_summary):
    rows = []

    for feature in state_lga_geojson["features"]:
        props = feature["properties"]

        rows.append(
            {
                "lga_geo_name": props["lga"],
                "lga_key": normalize_lga(props["state"], props["lga"]),
            }
        )

    map_df = pd.DataFrame(rows).merge(
        lga_summary,
        on="lga_key",
        how="left",
    )

    map_df["has_data"] = map_df["record_count"].notna()
    return map_df


def get_lga_navigation_options(lga_geojson, selected_state):
    """Return normalized LGA keys and display names for one state."""
    state_key = normalize_state(selected_state)
    labels = {}

    for feature in lga_geojson["features"]:
        props = feature["properties"]

        if normalize_state(props["state"]) == state_key:
            key = normalize_lga(props["state"], props["lga"])
            labels[key] = props["lga"]

    options = sorted(labels, key=lambda key: labels[key])
    return options, labels

# =========================================================
# CHARTS
# =========================================================

def apply_dark_map_layout(fig, risk_label):
    fig.update_layout(
        paper_bgcolor="#0b111b",
        plot_bgcolor="#0b111b",
        font=dict(color="#d9e2ef"),
        margin=dict(l=0, r=0, t=0, b=0),
        hoverlabel=dict(
            bgcolor="rgba(14,22,35,0.97)",
            bordercolor="rgba(255,255,255,0.15)",
            font=dict(color="#fff", size=13, family="Arial"),
            align="left",
        ),
        coloraxis_colorbar=dict(
            title=dict(
                text=risk_label,
                font=dict(color="#dce5f2", size=12),
            ),
            x=0.985,
            xanchor="right",
            y=0.50,
            len=0.53,
            thickness=12,
            bgcolor="rgba(10,16,26,0.72)",
            outlinewidth=0,
            tickfont=dict(color="#dce5f2", size=11),
        ),
        map=dict(domain=dict(x=[0, 1], y=[0, 1])),
    )

    return fig


def create_detail_pressure_chart(education_summary):
    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            name="Teacher Pressure",
            x=education_summary["education_level"],
            y=education_summary["Teacher Pressure"],
            marker_color="#78B4E8",
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Teacher Pressure: %{y:.2f}×"
                "<extra></extra>"
            ),
        )
    )

    fig.add_trace(
        go.Bar(
            name="Classroom Pressure",
            x=education_summary["education_level"],
            y=education_summary["Classroom Pressure"],
            marker_color="#156FC4",
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Classroom Pressure: %{y:.2f}×"
                "<extra></extra>"
            ),
        )
    )

    fig.add_hline(
        y=1,
        line_width=1,
        line_dash="dash",
        line_color="rgba(255,255,255,0.25)",
    )

    fig.update_layout(
        barmode="group",
        height=320,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        font=dict(color="#dbe5f2", size=12),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(color="#cfd9e8", size=12),
        ),
        hoverlabel=dict(
            bgcolor="rgba(14,22,35,0.97)",
            bordercolor="rgba(255,255,255,0.15)",
            font=dict(color="#fff", size=12),
        ),
        xaxis=dict(
            title=None,
            showgrid=False,
            tickfont=dict(color="#cdd7e5", size=12),
            zeroline=False,
        ),
        yaxis=dict(
            title="Pressure Index",
            showgrid=True,
            gridcolor="rgba(255,255,255,0.08)",
            tickfont=dict(color="#cdd7e5", size=12),
            title_font=dict(color="#94a4bc", size=12),
            zeroline=False,
        ),
    )

    return fig


def render_blended_table(df):
    html = df.to_html(
        index=False,
        classes="blend-table",
        border=0,
        escape=False,
    )

    st.markdown(
        f'<div class="table-shell">{html}</div>',
        unsafe_allow_html=True,
    )


def create_state_map(map_df, state_geojson, risk_column, risk_label):
    display_df = map_df.copy()

    display_df["severity"] = display_df[
        risk_column
    ].apply(classify_pressure)

    fig = px.choropleth_map(
        display_df,
        geojson=state_geojson,
        locations="state_name",
        featureidkey="properties.shapeName",
        color=risk_column,
        custom_data=[
            "state_name",
            risk_column,
            "severity",
            "data_confidence",
            "coverage_pct",
            "analysed_lgas",
            "total_lgas",
        ],
        color_continuous_scale=RISK_COLORS,
        range_color=(0, 3),
        map_style="carto-darkmatter",
        center={"lat": 9.0820, "lon": 8.6753},
        zoom=4.7,
        opacity=0.86,
        height=650,
    )

    fig.update_traces(
        marker_line_width=1.2,
        marker_line_color="#1c2533",
        hovertemplate=(
            "<b>%{customdata[0]}</b><br><br>"
            + risk_label
            + ": %{customdata[1]:.2f}×<br>"
            + "Severity: %{customdata[2]}<br>"
            + "Data confidence: %{customdata[3]}<br>"
            + "Coverage: %{customdata[4]:.0f}%<br>"
            + "LGAs represented: %{customdata[5]} / %{customdata[6]}"
            + "<extra></extra>"
        ),
    )

    return apply_dark_map_layout(fig, risk_label)


def create_lga_map(
    lga_map_df,
    state_lga_geojson,
    risk_column,
    risk_label,
):
    display_df = lga_map_df.copy()

    display_df["severity"] = display_df[
        risk_column
    ].apply(classify_pressure)

    coordinates = []

    def collect_coordinates(value):
        if (
            isinstance(value, list)
            and len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            coordinates.append((value[0], value[1]))
            return

        if isinstance(value, list):
            for item in value:
                collect_coordinates(item)

    for feature in state_lga_geojson["features"]:
        collect_coordinates(feature["geometry"]["coordinates"])

    if coordinates:
        longitudes = [point[0] for point in coordinates]
        latitudes = [point[1] for point in coordinates]

        min_lon, max_lon = min(longitudes), max(longitudes)
        min_lat, max_lat = min(latitudes), max(latitudes)

        center_lon = (min_lon + max_lon) / 2
        center_lat = (min_lat + max_lat) / 2

        span = max(
            max_lon - min_lon,
            max_lat - min_lat,
        )

        if span < 0.6:
            state_zoom = 8.2
        elif span < 1:
            state_zoom = 7.7
        elif span < 1.5:
            state_zoom = 7.2
        elif span < 2:
            state_zoom = 6.8
        elif span < 3:
            state_zoom = 6.4
        elif span < 4:
            state_zoom = 6.0
        else:
            state_zoom = 5.7

    else:
        center_lat = 9.0820
        center_lon = 8.6753
        state_zoom = 6.0

    fig = px.choropleth_map(
        display_df,
        geojson=state_lga_geojson,
        locations="lga_geo_name",
        featureidkey="properties.lga",
        color=risk_column,
        custom_data=[
            "lga_geo_name",
            "lga_key",
            risk_column,
            "severity",
            "record_count",
        ],
        color_continuous_scale=RISK_COLORS,
        range_color=(0, 3),
        map_style="carto-darkmatter",
        center={"lat": center_lat, "lon": center_lon},
        zoom=state_zoom,
        opacity=0.89,
        height=650,
    )

    fig.update_traces(
        marker_line_width=1.5,
        marker_line_color="#1a222f",
        hovertemplate=(
            "<b>%{customdata[0]}</b><br><br>"
            + risk_label
            + ": %{customdata[2]:.2f}×<br>"
            + "Severity: %{customdata[3]}<br>"
            + "Analyzable records: %{customdata[4]}"
            + "<extra></extra>"
        ),
    )

    return apply_dark_map_layout(fig, risk_label)

# =========================================================
# SESSION STATE
# =========================================================

if "view_level" not in st.session_state:
    st.session_state.view_level = "country"

if "selected_state" not in st.session_state:
    st.session_state.selected_state = None

if "selected_lga" not in st.session_state:
    st.session_state.selected_lga = None

if "risk_mode" not in st.session_state:
    st.session_state.risk_mode = "Overall Capacity Risk"

if "jump_state" not in st.session_state:
    st.session_state.jump_state = None

if "jump_lga" not in st.session_state:
    st.session_state.jump_lga = None


def select_risk_mode(mode):
    st.session_state.risk_mode = mode


def jump_to_state():
    """Navigate directly to the selected state."""
    selected_state = st.session_state.get("jump_state")

    st.session_state.selected_state = selected_state
    st.session_state.selected_lga = None
    st.session_state.jump_lga = None

    st.session_state.view_level = (
        "state" if selected_state else "country"
    )


def jump_to_lga():
    """Navigate directly to the selected LGA."""
    selected_lga = st.session_state.get("jump_lga")

    if selected_lga:
        st.session_state.selected_lga = selected_lga
        st.session_state.view_level = "lga"

# =========================================================
# LOAD DATA
# =========================================================

capacity_df = prepare_capacity_data(
    load_capacity_data()
)

state_geojson = load_state_geojson()
lga_geojson = load_lga_geojson()

lga_reference = build_lga_reference(
    lga_geojson
)

state_summary = build_state_summary(
    capacity_df,
    lga_reference,
)

state_map_df = build_state_map_dataframe(
    state_geojson,
    state_summary,
)

state_options = sorted(
    state_map_df["state_name"]
    .dropna()
    .unique()
    .tolist()
)

# Keep dropdowns synchronized with map navigation.
if st.session_state.selected_state in state_options:
    st.session_state.jump_state = (
        st.session_state.selected_state
    )

if st.session_state.view_level == "country":
    st.session_state.jump_state = None
    st.session_state.jump_lga = None

# =========================================================
# SIDEBAR NAVIGATION
# =========================================================

with st.sidebar:
    st.markdown(
        (
            '<div class="sidebar-brand">'
            '<div class="sidebar-brand-title">'
            "Nigerian Education<br>Capacity Monitor"
            "</div>"
            '<div class="sidebar-brand-subtitle">'
            "Education infrastructure and teacher distribution intelligence"
            "</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    st.markdown("---")

    st.markdown(
        '<div class="sidebar-section">Navigation</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.view_level != "country":
        if st.button(
            "⌂  National Overview",
            use_container_width=True,
            key="national_overview_button",
        ):
            st.session_state.view_level = "country"
            st.session_state.selected_state = None
            st.session_state.selected_lga = None
            st.session_state.jump_state = None
            st.session_state.jump_lga = None
            st.rerun()

    if st.session_state.view_level == "lga":
        if st.button(
            f"←  {st.session_state.selected_state}",
            use_container_width=True,
            key="back_to_state_button",
        ):
            st.session_state.view_level = "state"
            st.session_state.selected_lga = None
            st.session_state.jump_lga = None
            st.rerun()

    # -----------------------------------------------------
    # SEARCHABLE LOCATION NAVIGATION
    # -----------------------------------------------------

    st.markdown(
        '<div class="sidebar-section">Jump to Location</div>',
        unsafe_allow_html=True,
    )

    st.selectbox(
        "State",
        options=state_options,
        index=None,
        placeholder="Search or select a state",
        key="jump_state",
        on_change=jump_to_state,
    )

    active_state = st.session_state.get(
        "jump_state"
    )

    if active_state:
        lga_options, lga_labels = get_lga_navigation_options(
            lga_geojson,
            active_state,
        )

        if (
            st.session_state.selected_lga
            in lga_options
        ):
            st.session_state.jump_lga = (
                st.session_state.selected_lga
            )

        elif (
            st.session_state.jump_lga
            not in lga_options
        ):
            st.session_state.jump_lga = None

        st.selectbox(
            "LGA",
            options=lga_options,
            index=None,
            placeholder="Search or select an LGA",
            format_func=lambda key: lga_labels.get(key, key),
            key="jump_lga",
            on_change=jump_to_lga,
        )

    else:
        st.selectbox(
            "LGA",
            options=[],
            index=None,
            placeholder="Select a state first",
            disabled=True,
            key="jump_lga_disabled",
        )

    st.caption(
        "Type inside a dropdown to search."
    )

    # -----------------------------------------------------
    # RISK LAYER
    # -----------------------------------------------------

    st.markdown(
        '<div class="sidebar-section">Risk Layer</div>',
        unsafe_allow_html=True,
    )

    st.session_state["risk_overall"] = (
        st.session_state.risk_mode
        == "Overall Capacity Risk"
    )

    st.session_state["risk_teacher"] = (
        st.session_state.risk_mode
        == "Teacher Pressure"
    )

    st.session_state["risk_classroom"] = (
        st.session_state.risk_mode
        == "Classroom Overcrowding"
    )

    st.checkbox(
        "Overall Capacity Risk",
        key="risk_overall",
        on_change=select_risk_mode,
        args=("Overall Capacity Risk",),
    )

    st.checkbox(
        "Teacher Pressure",
        key="risk_teacher",
        on_change=select_risk_mode,
        args=("Teacher Pressure",),
    )

    st.checkbox(
        "Classroom Overcrowding",
        key="risk_classroom",
        on_change=select_risk_mode,
        args=("Classroom Overcrowding",),
    )

# =========================================================
# ACTIVE RISK LAYER
# =========================================================

risk_mode = st.session_state.risk_mode

if risk_mode == "Teacher Pressure":
    risk_column = "teacher_pressure"
    risk_label = "Teacher Pressure"

elif risk_mode == "Classroom Overcrowding":
    risk_column = "classroom_pressure"
    risk_label = "Classroom Pressure"

else:
    risk_column = "overall_pressure"
    risk_label = "Overall Capacity Risk"

# =========================================================
# SIDEBAR CONTEXT
# =========================================================

with st.sidebar:
    st.markdown(
        '<div class="sidebar-section">National Snapshot</div>',
        unsafe_allow_html=True,
    )

    snapshot1, snapshot2 = st.columns(2)

    snapshot1.metric(
        "Records",
        f"{len(capacity_df):,}",
    )

    snapshot2.metric(
        "LGAs",
        capacity_df["lga_key"].nunique(),
    )

    snapshot3, snapshot4 = st.columns(2)

    snapshot3.metric(
        "Teacher Alerts",
        f"{int(capacity_df['teacher_warning'].sum()):,}",
    )

    snapshot4.metric(
        "Classroom Alerts",
        f"{int(capacity_df['classroom_warning'].sum()):,}",
    )

    if st.session_state.view_level == "country":
        st.markdown(
            '<div class="sidebar-section">Highest Pressure States</div>',
            unsafe_allow_html=True,
        )

        ranking = (
            state_map_df[
                state_map_df[risk_column].notna()
            ]
            .sort_values(
                risk_column,
                ascending=False,
            )
            .head(7)
        )

        for _, row in ranking.iterrows():
            severity = classify_pressure(
                row[risk_column]
            )

            color = severity_color(
                severity
            )

            st.markdown(
                (
                    '<div class="sidebar-risk-row">'
                    "<span>"
                    '<span style="display:inline-block;'
                    "width:8px;height:8px;border-radius:50%;"
                    f'background:{color};margin-right:7px;"></span>'
                    f'{row["state_name"]}'
                    "</span>"
                    '<span class="sidebar-risk-score">'
                    f'{row[risk_column]:.2f}×'
                    "</span>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )

    elif st.session_state.selected_state:
        lga_sidebar_summary = build_lga_summary(
            capacity_df,
            st.session_state.selected_state,
        )

        st.markdown(
            (
                '<div class="sidebar-section">'
                f"{st.session_state.selected_state} LGAs"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

        if not lga_sidebar_summary.empty:
            ranking = (
                lga_sidebar_summary
                .sort_values(
                    risk_column,
                    ascending=False,
                )
                .head(7)
            )

            for _, row in ranking.iterrows():
                severity = classify_pressure(
                    row[risk_column]
                )

                color = severity_color(
                    severity
                )

                st.markdown(
                    (
                        '<div class="sidebar-risk-row">'
                        "<span>"
                        '<span style="display:inline-block;'
                        "width:8px;height:8px;border-radius:50%;"
                        f'background:{color};margin-right:7px;"></span>'
                        f'{row["dnemis_lga"]}'
                        "</span>"
                        '<span class="sidebar-risk-score">'
                        f'{row[risk_column]:.2f}×'
                        "</span>"
                        "</div>"
                    ),
                    unsafe_allow_html=True,
                )

    st.markdown("---")

    st.caption(
        "Source: Nigeria DNEMIS · 2024"
    )

    st.caption(
        "Benchmark: 35 learners per teacher/classroom"
    )

# =========================================================
# PAGE HEADER
# =========================================================

if st.session_state.view_level == "country":
    page_title = "National Education Capacity"
    page_subtitle = (
        "Monitor teacher distribution and "
        "classroom pressure across Nigeria."
    )

elif st.session_state.view_level == "state":
    page_title = (
        f"{st.session_state.selected_state} "
        "Education Capacity"
    )

    page_subtitle = (
        "Explore capacity pressure across "
        "Local Government Areas."
    )

else:
    page_title = "LGA Capacity Profile"

    page_subtitle = (
        f"{st.session_state.selected_state} · "
        "Detailed education capacity assessment"
    )

st.markdown(
    (
        f'<div class="dashboard-title">{page_title}</div>'
        f'<div class="dashboard-subtitle">{page_subtitle}</div>'
    ),
    unsafe_allow_html=True,
)

# =========================================================
# COUNTRY VIEW
# =========================================================

if st.session_state.view_level == "country":
    teacher_warnings = int(
        capacity_df["teacher_warning"].sum()
    )

    classroom_warnings = int(
        capacity_df["classroom_warning"].sum()
    )

    dual_warnings = int(
        (
            capacity_df["teacher_warning"]
            & capacity_df["classroom_warning"]
        ).sum()
    )

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    kpi1.metric(
        "Analyzable Records",
        f"{len(capacity_df):,}",
    )

    kpi2.metric(
        "Teacher Warnings",
        f"{teacher_warnings:,}",
    )

    kpi3.metric(
        "Classroom Warnings",
        f"{classroom_warnings:,}",
    )

    kpi4.metric(
        "Dual Warnings",
        f"{dual_warnings:,}",
    )

    st.markdown(
        '<div class="section-label">National Risk Map</div>',
        unsafe_allow_html=True,
    )

    st.caption(
        "Select a state on the map to drill down to its LGAs."
    )

    fig = create_state_map(
        state_map_df,
        state_geojson,
        risk_column,
        risk_label,
    )

    event = st.plotly_chart(
        fig,
        width="stretch",
        key="nigeria_map",
        on_select="rerun",
        selection_mode="points",
        config=MAP_CONFIG,
    )

    if (
        event
        and "selection" in event
        and event["selection"]["points"]
    ):
        point = event["selection"]["points"][0]
        selected_state = None

        if point.get("customdata"):
            selected_state = point["customdata"][0]

        elif point.get("location"):
            selected_state = point["location"]

        if selected_state:
            st.session_state.selected_state = selected_state
            st.session_state.selected_lga = None
            st.session_state.jump_state = selected_state
            st.session_state.jump_lga = None
            st.session_state.view_level = "state"
            st.rerun()

# =========================================================
# STATE VIEW
# =========================================================

elif st.session_state.view_level == "state":
    selected_state = st.session_state.selected_state
    selected_state_key = normalize_state(
        selected_state
    )

    state_data = capacity_df[
        capacity_df["state_key"]
        == selected_state_key
    ].copy()

    selected_summary = state_map_df[
        state_map_df["state_key"]
        == selected_state_key
    ]

    if not selected_summary.empty:
        state_row = selected_summary.iloc[0]
        state_pressure = state_row[risk_column]

        state_severity = classify_pressure(
            state_pressure
        )

        data_confidence = state_row[
            "data_confidence"
        ]

        coverage_pct = state_row[
            "coverage_pct"
        ]

        analysed_lgas = int(
            state_row["analysed_lgas"]
        )

        total_lgas = int(
            state_row["total_lgas"]
        )

        render_badges(
            state_severity,
            data_confidence,
        )

        st.caption(
            f"{coverage_pct:.0f}% geographic coverage · "
            f"{analysed_lgas} of {total_lgas} LGAs represented"
        )

    if state_data.empty:
        st.warning(
            "No complete DNEMIS capacity records "
            "are available for this state."
        )

    else:
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)

        kpi1.metric(
            "LGAs Represented",
            state_data["lga_key"].nunique(),
        )

        kpi2.metric(
            "Teacher Warnings",
            int(
                state_data[
                    "teacher_warning"
                ].sum()
            ),
        )

        kpi3.metric(
            "Classroom Warnings",
            int(
                state_data[
                    "classroom_warning"
                ].sum()
            ),
        )

        kpi4.metric(
            "Dual Warnings",
            int(
                (
                    state_data["teacher_warning"]
                    & state_data["classroom_warning"]
                ).sum()
            ),
        )

        lga_summary = build_lga_summary(
            capacity_df,
            selected_state,
        )

        state_lga_geojson = get_state_lga_geojson(
            lga_geojson,
            selected_state,
        )

        lga_map_df = build_lga_map_dataframe(
            state_lga_geojson,
            lga_summary,
        )

        st.markdown(
            '<div class="section-label">'
            "Local Government Risk Map"
            "</div>",
            unsafe_allow_html=True,
        )

        st.caption(
            "Select an LGA to open its detailed capacity profile."
        )

        lga_fig = create_lga_map(
            lga_map_df,
            state_lga_geojson,
            risk_column,
            risk_label,
        )

        lga_event = st.plotly_chart(
            lga_fig,
            width="stretch",
            key="lga_map",
            on_select="rerun",
            selection_mode="points",
            config=MAP_CONFIG,
        )

        if (
            lga_event
            and "selection" in lga_event
            and lga_event["selection"]["points"]
        ):
            point = lga_event[
                "selection"
            ]["points"][0]

            if point.get("customdata"):
                selected_lga = point[
                    "customdata"
                ][1]

                if selected_lga:
                    st.session_state.selected_lga = (
                        selected_lga
                    )

                    st.session_state.jump_lga = (
                        selected_lga
                    )

                    st.session_state.view_level = "lga"
                    st.rerun()

        no_data_lgas = lga_map_df[
            ~lga_map_df["has_data"]
        ]["lga_geo_name"].tolist()

        if no_data_lgas:
            with st.expander(
                "LGAs without complete capacity data"
            ):
                st.write(
                    ", ".join(
                        no_data_lgas
                    )
                )

# =========================================================
# LGA VIEW
# =========================================================

elif st.session_state.view_level == "lga":
    selected_state = (
        st.session_state.selected_state
    )

    selected_lga_key = (
        st.session_state.selected_lga
    )

    state_key = normalize_state(
        selected_state
    )

    lga_data = capacity_df[
        (
            capacity_df["state_key"]
            == state_key
        )
        & (
            capacity_df["lga_key"]
            == selected_lga_key
        )
    ].copy()

    if lga_data.empty:
        st.warning(
            "No complete capacity data is available for this LGA."
        )

    else:
        display_lga_name = (
            lga_data["lga"]
            .iloc[0]
        )

        st.markdown(
            (
                '<div style="font-size:1.55rem;font-weight:800;'
                'color:#f5f7fb;margin-bottom:8px;">'
                f"{display_lga_name}</div>"
            ),
            unsafe_allow_html=True,
        )

        teacher_pressure = (
            lga_data[
                "teacher_pressure_index"
            ]
            .quantile(0.75)
        )

        classroom_pressure = (
            lga_data[
                "classroom_pressure_index"
            ]
            .quantile(0.75)
        )

        overall_pressure = max(
            teacher_pressure,
            classroom_pressure,
        )

        severity = classify_pressure(
            overall_pressure
        )

        render_badges(
            severity
        )

        total_teacher_gap = (
            lga_data[
                "teacher_gap"
            ]
            .fillna(0)
            .sum()
        )

        total_learners = (
            lga_data[
                "learners"
            ]
            .fillna(0)
            .sum()
        )

        kpi1, kpi2, kpi3, kpi4 = (
            st.columns(4)
        )

        kpi1.metric(
            "Teacher Pressure",
            f"{teacher_pressure:.2f}×",
        )

        kpi2.metric(
            "Classroom Pressure",
            f"{classroom_pressure:.2f}×",
        )

        kpi3.metric(
            "Estimated Teacher Gap",
            f"{total_teacher_gap:,.0f}",
        )

        kpi4.metric(
            "Learners Represented",
            f"{total_learners:,.0f}",
        )

        # -------------------------------------------------
        # PRIORITY SEGMENT
        # -------------------------------------------------

        segment_df = lga_data.copy()

        segment_df["segment_pressure"] = (
            segment_df[
                [
                    "teacher_pressure_index",
                    "classroom_pressure_index",
                ]
            ]
            .max(axis=1)
        )

        worst_row = (
            segment_df
            .sort_values(
                "segment_pressure",
                ascending=False,
            )
            .iloc[0]
        )

        st.markdown(
            '<div class="section-label">Priority Signal</div>',
            unsafe_allow_html=True,
        )

        priority_html = (
            '<div class="info-card">'
            "<strong>Highest-pressure segment</strong>"
            "<br><br>"
            f'{worst_row["education_level"]} · '
            f'{worst_row["ownership"]}'
            "<br><br>"
            "Overall pressure: "
            f'<strong>{worst_row["segment_pressure"]:.2f}×</strong>'
            "&nbsp;&nbsp;&nbsp;"
            "Teacher: "
            f'<strong>{worst_row["teacher_pressure_index"]:.2f}×</strong>'
            "&nbsp;&nbsp;&nbsp;"
            "Classroom: "
            f'<strong>{worst_row["classroom_pressure_index"]:.2f}×</strong>'
            "</div>"
        )

        st.markdown(
            priority_html,
            unsafe_allow_html=True,
        )

        # -------------------------------------------------
        # PRESSURE CHART
        # -------------------------------------------------

        st.markdown(
            '<div class="section-label">'
            "Pressure by Education Level"
            "</div>",
            unsafe_allow_html=True,
        )

        education_summary = (
            lga_data
            .groupby(
                "education_level"
            )
            .agg(
                **{
                    "Teacher Pressure": (
                        "teacher_pressure_index",
                        "mean",
                    ),
                    "Classroom Pressure": (
                        "classroom_pressure_index",
                        "mean",
                    ),
                }
            )
            .reset_index()
            .round(2)
        )

        detail_chart = (
            create_detail_pressure_chart(
                education_summary
            )
        )

        st.plotly_chart(
            detail_chart,
            width="stretch",
            key="lga_detail_pressure_chart",
            config={"displayModeBar": False},
        )

        # -------------------------------------------------
        # TABLE
        # -------------------------------------------------

        st.markdown(
            '<div class="section-label">'
            "Capacity Breakdown"
            "</div>",
            unsafe_allow_html=True,
        )

        detail_table = lga_data[
            [
                "education_level",
                "ownership",
                "learners",
                "teachers",
                "source_learner_teacher_ratio",
                "teacher_gap",
                "teacher_pressure_index",
                "learners_per_classroom",
                "classroom_pressure_index",
                "teacher_warning",
                "classroom_warning",
            ]
        ].copy()

        detail_table["teacher_gap"] = (
            detail_table["teacher_gap"]
            .fillna(0)
            .round()
            .astype(int)
        )

        detail_table["learners"] = (
            detail_table["learners"]
            .fillna(0)
            .astype(int)
        )

        detail_table["teachers"] = (
            detail_table["teachers"]
            .fillna(0)
            .astype(int)
        )

        detail_table = detail_table.rename(
            columns={
                "education_level": "Level",
                "ownership": "Owner",
                "learners": "Learners",
                "teachers": "Teachers",
                "source_learner_teacher_ratio": "L/T Ratio",
                "teacher_gap": "T Gap",
                "teacher_pressure_index": "T Pressure",
                "learners_per_classroom": "L/Class",
                "classroom_pressure_index": "C Pressure",
                "teacher_warning": "T Warn",
                "classroom_warning": "C Warn",
            }
        )

        for column, decimals in {
            "L/T Ratio": 1,
            "T Pressure": 2,
            "L/Class": 1,
            "C Pressure": 2,
        }.items():
            detail_table[column] = (
                detail_table[column]
                .fillna(0)
                .round(decimals)
            )

        detail_table["T Warn"] = detail_table[
            "T Warn"
        ].map(
            lambda x: "Yes" if bool(x) else "No"
        )

        detail_table["C Warn"] = detail_table[
            "C Warn"
        ].map(
            lambda x: "Yes" if bool(x) else "No"
        )

        detail_table = detail_table.sort_values(
            "T Pressure",
            ascending=False,
        )

        render_blended_table(
            detail_table
        )

        # -------------------------------------------------
        # INTERPRETATION
        # -------------------------------------------------

        st.markdown(
            '<div class="section-label">Interpretation</div>',
            unsafe_allow_html=True,
        )

        if teacher_pressure > 1:
            st.write(
                f"Teacher pressure is "
                f"**{teacher_pressure:.2f}×** "
                "the 35 learners-per-teacher benchmark."
            )
        else:
            st.write(
                "Teacher capacity is within the benchmark "
                "based on the available data."
            )

        if classroom_pressure > 1:
            st.write(
                f"Classroom pressure is "
                f"**{classroom_pressure:.2f}×** "
                "the benchmark, indicating potential overcrowding."
            )
        else:
            st.write(
                "Classroom capacity is within the benchmark "
                "based on the available data."
            )

        if total_teacher_gap > 0:
            st.write(
                "The available records imply an estimated "
                f"teacher shortfall of approximately "
                f"**{total_teacher_gap:,.0f} teachers**."
            )

        st.caption(
            "A pressure index of 1.0 represents the benchmark "
            "of 35 learners per teacher or classroom."
        )