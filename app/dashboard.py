import copy
import os
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

st.set_page_config(page_title="Nigerian Education Capacity Monitor", page_icon="🇳🇬", layout="wide", initial_sidebar_state="expanded")

MAP_CONFIG = {"scrollZoom": False, "displayModeBar": True, "displaylogo": False, "modeBarButtonsToRemove": ["toImage", "resetViewMap"]}

st.markdown("""
<style>
:root{--background:#070d16;--sidebar:#09111d;--surface:#0f1826;--border:#223047;--text:#f3f6fb}
html,body,[data-testid="stAppViewContainer"],.stApp{background:var(--background);color:var(--text)}
[data-testid="stHeader"]{background:#070d16;border-bottom:1px solid #172232}
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
section[data-testid="stSidebar"] [data-testid="stCheckbox"]{margin:-5px 0}
section[data-testid="stSidebar"] [data-testid="stCheckbox"] p{color:#e0e7f1!important;font-size:.9rem;font-weight:500}
h1,h2,h3,h4{color:#f5f7fb!important} p{color:#a6b1c2}
.dashboard-title{color:#f5f7fb;font-size:2rem;font-weight:800;line-height:1.25;margin:0 0 6px}
.dashboard-subtitle{color:#8391a6;font-size:.97rem;margin-bottom:24px}
.section-label{color:#7788a0;text-transform:uppercase;letter-spacing:.09em;font-size:.72rem;font-weight:800;margin:21px 0 7px}
[data-testid="stMetric"]{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:16px 18px;box-shadow:0 8px 22px rgba(0,0,0,.15)}
[data-testid="stMetricLabel"],[data-testid="stMetricLabel"] p{color:#8594aa!important;font-weight:600}
[data-testid="stMetricValue"]{color:#f1f5fb;font-weight:800}
[data-testid="stPlotlyChart"]{background:transparent!important;border:none!important;box-shadow:none!important;padding:0!important}
.modebar{background:rgba(9,17,29,.88)!important;border-radius:9px!important;padding:3px!important}
.modebar-btn path{fill:#dce5f2!important}
[data-testid="stExpander"]{background:var(--surface);border:1px solid var(--border);border-radius:12px}
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
""", unsafe_allow_html=True)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_GEOJSON_PATH = PROJECT_ROOT / "data" / "reference" / "nigeria_states.geojson"
LGA_GEOJSON_PATH = PROJECT_ROOT / "data" / "reference" / "nigeria_lgas_enriched.geojson"

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "education_capacity")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_SSLMODE = os.getenv("DB_SSLMODE") or os.getenv("PGSSLMODE")

RISK_COLORS = [[0, "#2E8B57"], [.25, "#AFC75D"], [.5, "#E4C43F"], [.75, "#E77A35"], [1, "#C92B2B"]]

STATE_ALIASES = {
    "akwa ibom": "akwa ibom", "akwa-ibom": "akwa ibom", "anambra": "anambra",
    "anambra state": "anambra", "abuja federal capital territory": "federal capital territory",
    "federal capital territory": "federal capital territory",
}

LGA_ALIASES = {
    ("abia", "umu nneochi"): "umunneochi",
    ("federal capital territory", "municipal area council"): "abuja municipal area council",
    ("bayelsa", "yenegoa"): "yenagoa", ("benue", "oturkpo"): "otukpo",
    ("edo", "iguegben"): "igueben", ("ekiti", "gbonyin"): "aiyekire (gbonyin)",
    ("gombe", "shomgom"): "shongom", ("imo", "ezinihitte"): "ezinihitte mbaise",
    ("imo", "mbatoli"): "mbaitoli", ("jigawa", "biriniwa"): "birniwa",
    ("jigawa", "kiri kasama"): "kiri kasamma", ("kano", "danbatta"): "dambatta",
    ("kano", "garun malam"): "garun mallam", ("kano", "garum mallam"): "garun mallam",
    ("kano", "nassarawa"): "nasarawa", ("kebbi", "bagudu"): "bagudo",
    ("kebbi", "arewa"): "arewa dandi", ("kebbi", "danko wasagu"): "wasagu danko",
    ("nasarawa", "nasarawa eggon"): "nasarawa egon", ("niger", "muya"): "munya",
    ("ogun", "shagamu"): "sagamu", ("osun", "atakunmosa east"): "atakumosa east",
    ("osun", "atakunmosa west"): "atakumosa west", ("osun", "ayedade"): "ayedaade",
    ("osun", "ilesha east"): "ilesa east", ("osun", "ilesha west"): "ilesa west",
    ("sokoto", "wamakko"): "wamako", ("yobe", "bursari"): "busari",
    ("zamfara", "birnin magaji kiyaw"): "birnin magaji",
}


def normalize_name(value):
    if pd.isna(value): return None
    value = re.sub(r"[-/]", " ", str(value).strip().lower())
    value = re.sub(r"[.'’]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_state(value):
    value = normalize_name(value)
    return STATE_ALIASES.get(value, value)


def normalize_lga(state, lga):
    state_key, lga_key = normalize_state(state), normalize_name(lga)
    return LGA_ALIASES.get((state_key, lga_key), lga_key)


def classify_pressure(value):
    if pd.isna(value): return "No Data"
    if value <= 1: return "Normal"
    if value <= 1.5: return "Moderate"
    if value <= 2: return "High"
    if value <= 3: return "Severe"
    return "Critical"


def severity_color(value):
    return {"Normal": "#2E8B57", "Moderate": "#B89D24", "High": "#D8772D", "Severe": "#D64541", "Critical": "#9E2020", "No Data": "#586577"}.get(value, "#586577")


def confidence_color(value):
    return {"High": "#238A67", "Medium": "#B58D25", "Low": "#C96E2F", "No Data": "#586577", "Check Source": "#8B5FBF"}.get(value, "#586577")


def render_badges(severity=None, confidence=None):
    html = '<div class="badge-row">'
    if severity: html += f'<span class="dashboard-badge" style="background:{severity_color(severity)}">{severity} Capacity Pressure</span>'
    if confidence: html += f'<span class="dashboard-badge" style="background:{confidence_color(confidence)}">{confidence} Data Confidence</span>'
    st.markdown(html + "</div>", unsafe_allow_html=True)


def reporting_text(rate):
    return f"{rate:.1f}%" if pd.notna(rate) else "No Data"


def school_count_text(reported, expected):
    if pd.isna(reported) or pd.isna(expected): return "No Data"
    return f"{reported:,.0f} / {expected:,.0f}"


@st.cache_resource
def create_db_engine():
    if not DB_PASSWORD:
        st.error("DB_PASSWORD is not set.")
        st.stop()
    url = URL.create("postgresql+psycopg2", username=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT, database=DB_NAME)
    return create_engine(url, connect_args={"sslmode": DB_SSLMODE} if DB_SSLMODE else {})


@st.cache_data
def load_capacity_data():
    return pd.read_sql("SELECT * FROM capacity_metrics WHERE is_complete = TRUE", create_db_engine())


@st.cache_data
def load_reporting_data():
    return pd.read_sql("SELECT * FROM reporting_metrics", create_db_engine())


@st.cache_data
def load_state_geojson():
    import json
    with open(STATE_GEOJSON_PATH, "r", encoding="utf-8") as f: return json.load(f)


@st.cache_data
def load_lga_geojson():
    import json
    with open(LGA_GEOJSON_PATH, "r", encoding="utf-8") as f: return json.load(f)


def prepare_capacity_data(df):
    df = df.copy()
    df["state_key"] = df["state"].apply(normalize_state)
    df["lga_key"] = df.apply(lambda r: normalize_lga(r["state"], r["lga"]), axis=1)
    return df


def prepare_reporting_data(df):
    df = df.copy()
    df["state_key"] = df["state"].apply(normalize_state)
    df["lga_key"] = df.apply(lambda r: normalize_lga(r["state"], r["lga"]) if int(r["geo_level"]) == 3 else None, axis=1)
    return df


def build_lga_reference(geojson):
    return pd.DataFrame([{"state": f["properties"]["state"], "lga": f["properties"]["lga"]} for f in geojson["features"]])


def build_state_summary(capacity, lga_ref, reporting):
    ref = lga_ref.copy()
    ref["state_key"] = ref["state"].apply(normalize_state)
    ref["lga_key"] = ref.apply(lambda r: normalize_lga(r["state"], r["lga"]), axis=1)
    official = ref[["state_key", "lga_key"]].drop_duplicates()
    data_lgas = capacity[["state_key", "lga_key"]].drop_duplicates()
    matched = official.merge(data_lgas, on=["state_key", "lga_key"], how="inner")
    total = official.groupby("state_key")["lga_key"].nunique().rename("total_lgas")
    analysed = matched.groupby("state_key")["lga_key"].nunique().rename("analysed_lgas")
    metrics = capacity.groupby("state_key").agg(
        teacher_pressure=("teacher_pressure_index", lambda x: x.quantile(.75)),
        classroom_pressure=("classroom_pressure_index", lambda x: x.quantile(.75)),
        teacher_warnings=("teacher_warning", "sum"),
        classroom_warnings=("classroom_warning", "sum"),
        record_count=("lga", "size"),
    )
    out = pd.concat([metrics, total, analysed], axis=1).reset_index()
    out["total_lgas"] = out["total_lgas"].fillna(0).astype(int)
    out["analysed_lgas"] = out["analysed_lgas"].fillna(0).astype(int)
    out["coverage_pct"] = (out["analysed_lgas"] / out["total_lgas"].replace(0, pd.NA) * 100).fillna(0)
    out["overall_pressure"] = out[["teacher_pressure", "classroom_pressure"]].max(axis=1)
    rep = reporting[reporting["geo_level"] == 2][["state_key", "schools_reported", "schools_expected", "reporting_rate", "data_confidence", "reporting_valid"]]
    out = out.merge(rep, on="state_key", how="left")
    out["data_confidence"] = out["data_confidence"].fillna("No Data")
    return out


def build_state_map_dataframe(geojson, summary):
    rows = [{"state_name": f["properties"]["shapeName"], "state_key": normalize_state(f["properties"]["shapeName"])} for f in geojson["features"]]
    out = pd.DataFrame(rows).merge(summary, on="state_key", how="left")
    for c in ["coverage_pct", "analysed_lgas", "total_lgas"]: out[c] = out[c].fillna(0)
    out["data_confidence"] = out["data_confidence"].fillna("No Data")
    out["has_data"] = out["record_count"].notna()
    return out


def build_lga_summary(capacity, reporting, selected_state):
    state_key = normalize_state(selected_state)
    state_data = capacity[capacity["state_key"] == state_key]
    if state_data.empty:
        cap = pd.DataFrame(columns=["lga_key", "dnemis_lga", "teacher_pressure", "classroom_pressure", "teacher_warnings", "classroom_warnings", "record_count"])
    else:
        cap = state_data.groupby("lga_key").agg(
            dnemis_lga=("lga", "first"),
            teacher_pressure=("teacher_pressure_index", lambda x: x.quantile(.75)),
            classroom_pressure=("classroom_pressure_index", lambda x: x.quantile(.75)),
            teacher_warnings=("teacher_warning", "sum"),
            classroom_warnings=("classroom_warning", "sum"),
            record_count=("lga", "size"),
        ).reset_index()
    rep = reporting[(reporting["geo_level"] == 3) & (reporting["state_key"] == state_key)][["lga_key", "geo_name", "schools_reported", "schools_expected", "reporting_rate", "data_confidence", "reporting_valid"]]
    out = cap.merge(rep, on="lga_key", how="outer")
    out["overall_pressure"] = out[["teacher_pressure", "classroom_pressure"]].max(axis=1)
    out["data_confidence"] = out["data_confidence"].fillna("No Data")
    return out


def get_state_lga_geojson(geojson, selected_state):
    key = normalize_state(selected_state)
    return {"type": "FeatureCollection", "features": [copy.deepcopy(f) for f in geojson["features"] if normalize_state(f["properties"]["state"]) == key]}


def build_lga_map_dataframe(state_geojson, summary):
    rows = [{"lga_geo_name": f["properties"]["lga"], "lga_key": normalize_lga(f["properties"]["state"], f["properties"]["lga"])} for f in state_geojson["features"]]
    out = pd.DataFrame(rows).merge(summary, on="lga_key", how="left")
    out["has_data"] = out["record_count"].notna()
    out["data_confidence"] = out["data_confidence"].fillna("No Data")
    return out


def get_lga_navigation_options(geojson, selected_state):
    key, labels = normalize_state(selected_state), {}
    for f in geojson["features"]:
        p = f["properties"]
        if normalize_state(p["state"]) == key: labels[normalize_lga(p["state"], p["lga"])] = p["lga"]
    return sorted(labels, key=lambda x: labels[x]), labels


def apply_dark_map_layout(fig, label):
    fig.update_layout(
        paper_bgcolor="#0b111b", plot_bgcolor="#0b111b", font=dict(color="#d9e2ef"), margin=dict(l=0, r=0, t=0, b=0),
        hoverlabel=dict(bgcolor="rgba(14,22,35,.97)", bordercolor="rgba(255,255,255,.15)", font=dict(color="#fff", size=13)),
        coloraxis_colorbar=dict(title=dict(text=label, font=dict(color="#dce5f2", size=12)), x=.985, xanchor="right", y=.5, len=.53, thickness=12, bgcolor="rgba(10,16,26,.72)", outlinewidth=0, tickfont=dict(color="#dce5f2", size=11)),
    )
    return fig


def create_state_map(df, geojson, risk_column, label):
    d = df.copy()
    d["severity"] = d[risk_column].apply(classify_pressure)
    d["risk_display"] = d[risk_column].apply(lambda x: f"{x:.2f}×" if pd.notna(x) else "No Data")
    d["reporting_display"] = d["reporting_rate"].apply(reporting_text)
    d["schools_display"] = d.apply(lambda r: school_count_text(r["schools_reported"], r["schools_expected"]), axis=1)
    d["coverage_display"] = d["coverage_pct"].apply(lambda x: f"{x:.0f}%")
    d["lga_display"] = d.apply(lambda r: f"{int(r['analysed_lgas'])} / {int(r['total_lgas'])}", axis=1)
    fig = px.choropleth_map(
        d, geojson=geojson, locations="state_name", featureidkey="properties.shapeName", color=risk_column,
        custom_data=["state_name", "risk_display", "severity", "data_confidence", "reporting_display", "schools_display", "coverage_display", "lga_display"],
        color_continuous_scale=RISK_COLORS, range_color=(0, 3), map_style="carto-darkmatter",
        center={"lat": 9.082, "lon": 8.6753}, zoom=4.7, opacity=.86, height=650,
    )
    fig.update_traces(marker_line_width=1.2, marker_line_color="#1c2533", hovertemplate="<b>%{customdata[0]}</b><br><br>"+label+": %{customdata[1]}<br>Severity: %{customdata[2]}<br>Data confidence: %{customdata[3]}<br>Reporting rate: %{customdata[4]}<br>Schools reported/expected: %{customdata[5]}<br>Capacity geographic coverage: %{customdata[6]}<br>LGAs with capacity data: %{customdata[7]}<extra></extra>")
    return apply_dark_map_layout(fig, label)


def create_lga_map(df, geojson, risk_column, label):
    d = df.copy()
    d["severity"] = d[risk_column].apply(classify_pressure)
    d["risk_display"] = d[risk_column].apply(lambda x: f"{x:.2f}×" if pd.notna(x) else "No Data")
    d["reporting_display"] = d["reporting_rate"].apply(reporting_text)
    d["schools_display"] = d.apply(lambda r: school_count_text(r["schools_reported"], r["schools_expected"]), axis=1)
    coords = []

    def collect(v):
        if isinstance(v, list) and len(v) >= 2 and all(isinstance(x, (int, float)) for x in v[:2]): coords.append((v[0], v[1]))
        elif isinstance(v, list):
            for x in v: collect(x)

    for f in geojson["features"]: collect(f["geometry"]["coordinates"])
    if coords:
        lon, lat = [x[0] for x in coords], [x[1] for x in coords]
        center_lon, center_lat = (min(lon) + max(lon)) / 2, (min(lat) + max(lat)) / 2
        span = max(max(lon) - min(lon), max(lat) - min(lat))
        zoom = 8.2 if span < .6 else 7.7 if span < 1 else 7.2 if span < 1.5 else 6.8 if span < 2 else 6.4 if span < 3 else 6 if span < 4 else 5.7
    else: center_lat, center_lon, zoom = 9.082, 8.6753, 6
    fig = px.choropleth_map(
        d, geojson=geojson, locations="lga_geo_name", featureidkey="properties.lga", color=risk_column,
        custom_data=["lga_geo_name", "lga_key", "risk_display", "severity", "data_confidence", "reporting_display", "schools_display"],
        color_continuous_scale=RISK_COLORS, range_color=(0, 3), map_style="carto-darkmatter",
        center={"lat": center_lat, "lon": center_lon}, zoom=zoom, opacity=.89, height=650,
    )
    fig.update_traces(marker_line_width=1.5, marker_line_color="#1a222f", hovertemplate="<b>%{customdata[0]}</b><br><br>"+label+": %{customdata[2]}<br>Severity: %{customdata[3]}<br>Data confidence: %{customdata[4]}<br>Reporting rate: %{customdata[5]}<br>Schools reported/expected: %{customdata[6]}<extra></extra>")
    return apply_dark_map_layout(fig, label)


def create_detail_pressure_chart(df):
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Teacher Pressure", x=df["education_level"], y=df["Teacher Pressure"], marker_color="#78B4E8"))
    fig.add_trace(go.Bar(name="Classroom Pressure", x=df["education_level"], y=df["Classroom Pressure"], marker_color="#156FC4"))
    fig.add_hline(y=1, line_width=1, line_dash="dash", line_color="rgba(255,255,255,.25)")
    fig.update_layout(barmode="group", height=320, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10), font=dict(color="#dbe5f2"), legend=dict(orientation="h", y=1.02, x=0), yaxis=dict(title="Pressure Index", gridcolor="rgba(255,255,255,.08)"), xaxis=dict(title=None, showgrid=False))
    return fig


def render_table(df):
    st.markdown(f'<div class="table-shell">{df.to_html(index=False, classes="blend-table", border=0, escape=False)}</div>', unsafe_allow_html=True)


for key, value in {
    "view_level": "country", "selected_state": None, "selected_lga": None,
    "risk_mode": "Overall Capacity Risk", "jump_state": None, "jump_lga": None,
}.items():
    if key not in st.session_state: st.session_state[key] = value


def select_risk_mode(mode): st.session_state.risk_mode = mode


def jump_to_state():
    state = st.session_state.get("jump_state")
    st.session_state.selected_state, st.session_state.selected_lga, st.session_state.jump_lga = state, None, None
    st.session_state.view_level = "state" if state else "country"


def jump_to_lga():
    lga = st.session_state.get("jump_lga")
    if lga: st.session_state.selected_lga, st.session_state.view_level = lga, "lga"


capacity_df = prepare_capacity_data(load_capacity_data())
reporting_df = prepare_reporting_data(load_reporting_data())
latest_year = int(capacity_df["year"].max())
capacity_df = capacity_df[capacity_df["year"] == latest_year].copy()
reporting_df = reporting_df[reporting_df["year"] == latest_year].copy()

state_geojson, lga_geojson = load_state_geojson(), load_lga_geojson()
lga_reference = build_lga_reference(lga_geojson)
state_summary = build_state_summary(capacity_df, lga_reference, reporting_df)
state_map_df = build_state_map_dataframe(state_geojson, state_summary)
state_options = sorted(state_map_df["state_name"].dropna().unique())

if st.session_state.selected_state in state_options: st.session_state.jump_state = st.session_state.selected_state
if st.session_state.view_level == "country": st.session_state.jump_state, st.session_state.jump_lga = None, None

with st.sidebar:
    st.markdown('<div class="sidebar-brand"><div class="sidebar-brand-title">Nigerian Education<br>Capacity Monitor</div><div class="sidebar-brand-subtitle">Education infrastructure and teacher distribution intelligence</div></div>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown('<div class="sidebar-section">Navigation</div>', unsafe_allow_html=True)

    if st.session_state.view_level != "country" and st.button("⌂  National Overview", use_container_width=True):
        st.session_state.view_level, st.session_state.selected_state, st.session_state.selected_lga = "country", None, None
        st.session_state.jump_state, st.session_state.jump_lga = None, None
        st.rerun()

    if st.session_state.view_level == "lga" and st.button(f"←  {st.session_state.selected_state}", use_container_width=True):
        st.session_state.view_level, st.session_state.selected_lga, st.session_state.jump_lga = "state", None, None
        st.rerun()

    st.markdown('<div class="sidebar-section">Jump to Location</div>', unsafe_allow_html=True)
    st.selectbox("State", state_options, index=None, placeholder="Search or select a state", key="jump_state", on_change=jump_to_state)
    active_state = st.session_state.get("jump_state")

    if active_state:
        lga_options, lga_labels = get_lga_navigation_options(lga_geojson, active_state)
        if st.session_state.selected_lga in lga_options: st.session_state.jump_lga = st.session_state.selected_lga
        elif st.session_state.jump_lga not in lga_options: st.session_state.jump_lga = None
        st.selectbox("LGA", lga_options, index=None, placeholder="Search or select an LGA", format_func=lambda x: lga_labels.get(x, x), key="jump_lga", on_change=jump_to_lga)
    else:
        st.selectbox("LGA", [], index=None, placeholder="Select a state first", disabled=True, key="jump_lga_disabled")

    st.markdown('<div class="sidebar-section">Risk Layer</div>', unsafe_allow_html=True)
    st.session_state["risk_overall"] = st.session_state.risk_mode == "Overall Capacity Risk"
    st.session_state["risk_teacher"] = st.session_state.risk_mode == "Teacher Pressure"
    st.session_state["risk_classroom"] = st.session_state.risk_mode == "Classroom Overcrowding"
    st.checkbox("Overall Capacity Risk", key="risk_overall", on_change=select_risk_mode, args=("Overall Capacity Risk",))
    st.checkbox("Teacher Pressure", key="risk_teacher", on_change=select_risk_mode, args=("Teacher Pressure",))
    st.checkbox("Classroom Overcrowding", key="risk_classroom", on_change=select_risk_mode, args=("Classroom Overcrowding",))

risk_mode = st.session_state.risk_mode
risk_column, risk_label = (
    ("teacher_pressure", "Teacher Pressure") if risk_mode == "Teacher Pressure"
    else ("classroom_pressure", "Classroom Pressure") if risk_mode == "Classroom Overcrowding"
    else ("overall_pressure", "Overall Capacity Risk")
)

with st.sidebar:
    st.markdown('<div class="sidebar-section">National Snapshot</div>', unsafe_allow_html=True)
    a, b = st.columns(2)
    a.metric("Records", f"{len(capacity_df):,}")
    b.metric("LGAs", capacity_df["lga_key"].nunique())
    c, d = st.columns(2)
    c.metric("Teacher Alerts", f"{int(capacity_df['teacher_warning'].sum()):,}")
    d.metric("Classroom Alerts", f"{int(capacity_df['classroom_warning'].sum()):,}")

    if st.session_state.view_level == "country":
        st.markdown('<div class="sidebar-section">Highest Pressure States</div>', unsafe_allow_html=True)
        ranking = state_map_df[state_map_df[risk_column].notna()].sort_values(risk_column, ascending=False).head(7)
        for _, r in ranking.iterrows():
            color = severity_color(classify_pressure(r[risk_column]))
            st.markdown(f'<div class="sidebar-risk-row"><span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{color};margin-right:7px"></span>{r["state_name"]}</span><span class="sidebar-risk-score">{r[risk_column]:.2f}×</span></div>', unsafe_allow_html=True)
    elif st.session_state.selected_state:
        ranking = build_lga_summary(capacity_df, reporting_df, st.session_state.selected_state)
        ranking = ranking[ranking[risk_column].notna()].sort_values(risk_column, ascending=False).head(7)
        st.markdown(f'<div class="sidebar-section">{st.session_state.selected_state} LGAs</div>', unsafe_allow_html=True)
        for _, r in ranking.iterrows():
            name = r["dnemis_lga"] if pd.notna(r["dnemis_lga"]) else r["geo_name"]
            color = severity_color(classify_pressure(r[risk_column]))
            st.markdown(f'<div class="sidebar-risk-row"><span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{color};margin-right:7px"></span>{name}</span><span class="sidebar-risk-score">{r[risk_column]:.2f}×</span></div>', unsafe_allow_html=True)

    st.markdown("---")
    st.caption(f"Source: Nigeria DNEMIS · {latest_year}")
    st.caption("Benchmark: 35 learners per teacher/classroom")
    st.caption("Data confidence: school reporting rate")

view = st.session_state.view_level
if view == "country":
    page_title, page_subtitle = "National Education Capacity", "Monitor teacher distribution and classroom pressure across Nigeria."
elif view == "state":
    page_title, page_subtitle = f"{st.session_state.selected_state} Education Capacity", "Explore capacity pressure across Local Government Areas."
else:
    page_title, page_subtitle = "LGA Capacity Profile", f"{st.session_state.selected_state} · Detailed education capacity assessment"

st.markdown(f'<div class="dashboard-title">{page_title}</div><div class="dashboard-subtitle">{page_subtitle}</div>', unsafe_allow_html=True)

if view == "country":
    national = reporting_df[reporting_df["geo_level"] == 1].iloc[0]
    teacher_q75 = capacity_df["teacher_pressure_index"].quantile(.75)
    classroom_q75 = capacity_df["classroom_pressure_index"].quantile(.75)
    national_pressure = max(teacher_q75, classroom_q75)

    render_badges(classify_pressure(national_pressure), national["data_confidence"])
    st.caption(f"Reporting rate: {national['reporting_rate']:.1f}% · {national['schools_reported']:,.0f} of {national['schools_expected']:,.0f} expected schools reported")

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Analyzable Records", f"{len(capacity_df):,}")
    k2.metric("Reporting Rate", f"{national['reporting_rate']:.1f}%")
    k3.metric("Teacher Warnings", f"{int(capacity_df['teacher_warning'].sum()):,}")
    k4.metric("Classroom Warnings", f"{int(capacity_df['classroom_warning'].sum()):,}")
    k5.metric("Dual Warnings", f"{int((capacity_df['teacher_warning'] & capacity_df['classroom_warning']).sum()):,}")

    st.markdown('<div class="section-label">National Risk Map</div>', unsafe_allow_html=True)
    st.caption("Select a state on the map to drill down to its LGAs.")
    event = st.plotly_chart(create_state_map(state_map_df, state_geojson, risk_column, risk_label), width="stretch", key="nigeria_map", on_select="rerun", selection_mode="points", config=MAP_CONFIG)

    if event and event["selection"]["points"]:
        p = event["selection"]["points"][0]
        selected = p.get("customdata", [None])[0] if p.get("customdata") else p.get("location")
        if selected:
            st.session_state.selected_state, st.session_state.selected_lga, st.session_state.view_level = selected, None, "state"
            st.rerun()

elif view == "state":
    selected_state = st.session_state.selected_state
    state_key = normalize_state(selected_state)
    state_data = capacity_df[capacity_df["state_key"] == state_key]
    state_row = state_map_df[state_map_df["state_key"] == state_key].iloc[0]

    pressure = state_row[risk_column]
    render_badges(classify_pressure(pressure), state_row["data_confidence"])
    st.caption(
        f"Reporting rate: {reporting_text(state_row['reporting_rate'])} · "
        f"{school_count_text(state_row['schools_reported'], state_row['schools_expected'])} schools reported/expected · "
        f"Capacity geographic coverage: {state_row['coverage_pct']:.0f}% · "
        f"{int(state_row['analysed_lgas'])} of {int(state_row['total_lgas'])} LGAs with capacity data"
    )

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("LGAs with Data", int(state_row["analysed_lgas"]))
    k2.metric("Reporting Rate", reporting_text(state_row["reporting_rate"]))
    k3.metric("Teacher Alerts", int(state_data["teacher_warning"].sum()))
    k4.metric("Classroom Alerts", int(state_data["classroom_warning"].sum()))
    k5.metric("Dual Alerts", int((state_data["teacher_warning"] & state_data["classroom_warning"]).sum()))

    lga_summary = build_lga_summary(capacity_df, reporting_df, selected_state)
    state_lga_geojson = get_state_lga_geojson(lga_geojson, selected_state)
    lga_map_df = build_lga_map_dataframe(state_lga_geojson, lga_summary)

    st.markdown('<div class="section-label">Local Government Risk Map</div>', unsafe_allow_html=True)
    st.caption("Select an LGA to open its detailed capacity and reporting profile.")
    event = st.plotly_chart(create_lga_map(lga_map_df, state_lga_geojson, risk_column, risk_label), width="stretch", key="lga_map", on_select="rerun", selection_mode="points", config=MAP_CONFIG)

    if event and event["selection"]["points"]:
        p = event["selection"]["points"][0]
        if p.get("customdata"):
            selected_lga = p["customdata"][1]
            if selected_lga:
                st.session_state.selected_lga, st.session_state.view_level = selected_lga, "lga"
                st.rerun()

    missing = lga_map_df[~lga_map_df["has_data"]]["lga_geo_name"].tolist()
    if missing:
        with st.expander("LGAs without complete capacity data"): st.write(", ".join(missing))

elif view == "lga":
    selected_state, selected_lga = st.session_state.selected_state, st.session_state.selected_lga
    state_key = normalize_state(selected_state)
    lga_data = capacity_df[(capacity_df["state_key"] == state_key) & (capacity_df["lga_key"] == selected_lga)].copy()
    rep_rows = reporting_df[(reporting_df["geo_level"] == 3) & (reporting_df["state_key"] == state_key) & (reporting_df["lga_key"] == selected_lga)]
    rep = rep_rows.iloc[0] if not rep_rows.empty else None
    display_name = lga_data["lga"].iloc[0] if not lga_data.empty else rep["geo_name"] if rep is not None else selected_lga.title()

    st.markdown(f'<div style="font-size:1.55rem;font-weight:800;color:#f5f7fb;margin-bottom:8px">{display_name}</div>', unsafe_allow_html=True)

    confidence = rep["data_confidence"] if rep is not None else "No Data"

    if lga_data.empty:
        render_badges(confidence=confidence)
        if rep is not None:
            a, b, c = st.columns(3)
            a.metric("Reporting Rate", reporting_text(rep["reporting_rate"]))
            b.metric("Schools Reported", f"{rep['schools_reported']:,.0f}")
            c.metric("Schools Expected", f"{rep['schools_expected']:,.0f}")
            if confidence == "Check Source": st.warning("DNEMIS reports more schools reported than expected for this LGA. The reporting rate is retained for QA but is not treated as high confidence.")
        st.warning("No complete teacher/classroom capacity records are available for this LGA.")

    else:
        teacher_pressure = lga_data["teacher_pressure_index"].quantile(.75)
        classroom_pressure = lga_data["classroom_pressure_index"].quantile(.75)
        overall_pressure = max(teacher_pressure, classroom_pressure)
        render_badges(classify_pressure(overall_pressure), confidence)

        if rep is not None:
            st.caption(f"Reporting rate: {reporting_text(rep['reporting_rate'])} · {school_count_text(rep['schools_reported'], rep['schools_expected'])} schools reported/expected")
            if confidence == "Check Source": st.warning("DNEMIS reports more schools reported than expected for this LGA. The reporting rate is retained for QA but is not classified as high confidence.")

        teacher_gap = lga_data["teacher_gap"].fillna(0).sum()
        learners = lga_data["learners"].fillna(0).sum()
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Teacher Pressure", f"{teacher_pressure:.2f}×")
        k2.metric("Classroom Pressure", f"{classroom_pressure:.2f}×")
        k3.metric("Reporting Rate", reporting_text(rep["reporting_rate"]) if rep is not None else "No Data")
        k4.metric("Estimated Teacher Gap", f"{teacher_gap:,.0f}")
        k5.metric("Learners Represented", f"{learners:,.0f}")

        segment = lga_data.copy()
        segment["segment_pressure"] = segment[["teacher_pressure_index", "classroom_pressure_index"]].max(axis=1)
        worst = segment.sort_values("segment_pressure", ascending=False).iloc[0]

        st.markdown('<div class="section-label">Priority Signal</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="info-card"><strong>Highest-pressure segment</strong><br><br>{worst["education_level"]} · {worst["ownership"]}<br><br>'
            f'Overall pressure: <strong>{worst["segment_pressure"]:.2f}×</strong>&nbsp;&nbsp;&nbsp;Teacher: <strong>{worst["teacher_pressure_index"]:.2f}×</strong>&nbsp;&nbsp;&nbsp;Classroom: <strong>{worst["classroom_pressure_index"]:.2f}×</strong></div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div class="section-label">Pressure by Education Level</div>', unsafe_allow_html=True)
        education_summary = lga_data.groupby("education_level").agg(
            **{"Teacher Pressure": ("teacher_pressure_index", "mean"), "Classroom Pressure": ("classroom_pressure_index", "mean")}
        ).reset_index().round(2)
        st.plotly_chart(create_detail_pressure_chart(education_summary), width="stretch", config={"displayModeBar": False})

        st.markdown('<div class="section-label">Capacity Breakdown</div>', unsafe_allow_html=True)
        table = lga_data[[
            "education_level", "ownership", "learners", "teachers", "source_learner_teacher_ratio",
            "teacher_gap", "teacher_pressure_index", "learners_per_classroom",
            "classroom_pressure_index", "teacher_warning", "classroom_warning",
        ]].copy()

        table["teacher_gap"] = table["teacher_gap"].fillna(0).round().astype(int)
        table["learners"] = table["learners"].fillna(0).astype(int)
        table["teachers"] = table["teachers"].fillna(0).astype(int)
        table = table.rename(columns={
            "education_level": "Level", "ownership": "Owner", "learners": "Learners",
            "teachers": "Teachers", "source_learner_teacher_ratio": "L/T Ratio",
            "teacher_gap": "T Gap", "teacher_pressure_index": "T Pressure",
            "learners_per_classroom": "L/Class", "classroom_pressure_index": "C Pressure",
            "teacher_warning": "T Warn", "classroom_warning": "C Warn",
        })

        for col, decimals in {"L/T Ratio": 1, "T Pressure": 2, "L/Class": 1, "C Pressure": 2}.items():
            table[col] = table[col].fillna(0).round(decimals)

        table["T Warn"] = table["T Warn"].map(lambda x: "Yes" if bool(x) else "No")
        table["C Warn"] = table["C Warn"].map(lambda x: "Yes" if bool(x) else "No")
        render_table(table.sort_values("T Pressure", ascending=False))

        st.markdown('<div class="section-label">Interpretation</div>', unsafe_allow_html=True)
        st.write(
            f"Teacher pressure is **{teacher_pressure:.2f}×** the benchmark."
            if teacher_pressure > 1 else
            "Teacher capacity is within the benchmark based on the available data."
        )
        st.write(
            f"Classroom pressure is **{classroom_pressure:.2f}×** the benchmark, indicating potential overcrowding."
            if classroom_pressure > 1 else
            "Classroom capacity is within the benchmark based on the available data."
        )
        if teacher_gap > 0: st.write(f"The available records imply an estimated teacher shortfall of approximately **{teacher_gap:,.0f} teachers**.")
        st.caption("A pressure index of 1.0 represents the benchmark of 35 learners per teacher or classroom.")