from __future__ import annotations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from simulation.map_utils import circle_polygon, hex_polygon
from simulation.visibility_engine import run_visibility_engine
from simulation.beam_model import generate_beam_codebook, evaluate_terminal_against_beams
from datetime import datetime, timezone, timedelta
import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st
import yaml
from skyfield.api import Topos, load
from simulation.visibility_engine import run_visibility_engine  # noqa: E402

st.set_page_config(page_title="LEO Resilience Studio", layout="wide")
st.title("LEO Link Resilience Toolkit")
st.caption("Designed by: Hamidreza Saberkari, PhD")

#scenario_default = ROOT / "simulation/sample_scenarios/northern_quebec_starlink_like.yaml"
#scenario_path = scenario_default
#st.sidebar.caption("Scenario: Northern Quebec Starlink simulation")

scenario_files = {
    "Northern Quebec": ROOT / "simulation/sample_scenarios/northern_quebec_starlink_like.yaml"
}

scenario_name = st.sidebar.selectbox("Scenario", list(scenario_files.keys()))
scenario_path = scenario_files[scenario_name]

max_sats = st.sidebar.slider("Max satellites for dashboard demo", 50, 1000, 300, 50)
elev_visible = st.sidebar.slider("Visible threshold (deg)", 0, 30, 5, 1)
elev_service = st.sidebar.slider("Service threshold (deg)", 0, 40, 20, 1)
beam_service_threshold = st.sidebar.slider(
    "Beam service score threshold",
    0.0,
    1.0,
    0.35,
    0.01,
)
prediction_horizon_steps = st.sidebar.slider("Imminent outage look-ahead (steps)", 1, 5, 3, 1)
time_mode = st.sidebar.radio(
    "Time mode",
    ["Scenario", "Forecast from now"],
    index=0,
)

forecast_duration_min = st.sidebar.slider("Forecast duration (min)", 10, 180, 60, 10)
step_seconds = st.sidebar.slider("Forecast step size (s)", 10, 120, 30, 10)

rf_params = {
    "carrier_frequency_hz": 12e9,
    "channel_bandwidth_hz": 100e6,
    "sat_eirp_dbw": 55.0,
    "terminal_gain_dbi": 35.0,
    "noise_figure_db": 3.0,
    "sinr_service_threshold_db": 3.0,
    "interference_margin_db": 2.0,
}

if st.sidebar.button("Load live Starlink TLE path"):
    st.sidebar.info(
        "Tip: for faster dashboard runs, use simulation/sample_scenarios/starlink_demo_80.tle."
    )

scenario_file = Path(scenario_path)
if not scenario_file.exists():
    st.error(f"Scenario file not found: {scenario_file}")
    st.stop()


@st.cache_data(show_spinner=False)
def load_config(path_str: str) -> dict:
    return yaml.safe_load(Path(path_str).read_text(encoding="utf-8"))


@st.cache_data(show_spinner=True)
def run_visibility_cached(
    path_str: str,
    time_mode: str,
    forecast_duration_min: int,
    step_seconds: int,
) -> pd.DataFrame:
    config_local = load_config(path_str)

    if time_mode == "Forecast from now":
        config_local["simulation"]["start_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        config_local["simulation"]["duration_s"] = int(forecast_duration_min * 60)
        config_local["simulation"]["step_s"] = int(step_seconds)

    rows_local = run_visibility_engine(config_local)
    df_local = pd.DataFrame(rows_local)

    if not df_local.empty:
        df_local["timestamp_utc"] = pd.to_datetime(df_local["timestamp_utc"])

    return df_local


@st.cache_data(show_spinner=False)
def build_satellite_points(path_str: str, selected_time_str: str, max_satellites: int) -> pd.DataFrame:
    config_local = load_config(path_str)
    region_local = config_local["region"]

    ts = load.timescale()
    observer = Topos(
        latitude_degrees=region_local["latitude_deg"],
        longitude_degrees=region_local["longitude_deg"],
        elevation_m=region_local.get("altitude_m", 0),
    )

    current_dt = pd.Timestamp(selected_time_str).to_pydatetime().astimezone(timezone.utc)

    tle_file = ROOT / config_local["constellation"].get(
        "tle_file", "simulation/sample_scenarios/sample.tle"
    )
    satellites = load.tle_file(str(tle_file))[:max_satellites]
    t = ts.from_datetime(current_dt)

    sat_points_local = []
    for sat in satellites:
        geocentric = sat.at(t)
        sp = geocentric.subpoint()

        difference = sat - observer
        topocentric = difference.at(t)
        alt, az, distance = topocentric.altaz()

        sat_points_local.append(
            {
                "name": sat.name,
                "lat": sp.latitude.degrees,
                "lon": sp.longitude.degrees,
                "alt_m": max(1000, geocentric.distance().km * 10),
                "elevation_deg": round(alt.degrees, 3),
                "azimuth_deg": round(az.degrees, 3),
                "range_km": round(distance.km, 3),
            }
        )

    return pd.DataFrame(sat_points_local)

config = load_config(str(scenario_file))

if time_mode == "Forecast from now":
    st.info("Forecast mode: simulating from current UTC time forward.")
else:
    st.info("Scenario mode: using the fixed time window from the YAML scenario.")

with st.spinner("Running visibility simulation..."):
    df = run_visibility_cached(
        str(scenario_file),
        time_mode,
        forecast_duration_min,
        step_seconds,
    )

if df.empty:
    st.warning("No visible satellites found for this scenario.")
    st.stop()

all_times = sorted(df["timestamp_utc"].unique())

timeline_rows = []
terminal_lat = config["region"]["latitude_deg"]
terminal_lon = config["region"]["longitude_deg"]

for ts in all_times:
    snap_df = df[df["timestamp_utc"] == pd.Timestamp(ts)].copy()
    snap_sat_df = build_satellite_points(str(scenario_file), str(ts), max_sats)

    available_names = set(snap_sat_df["name"].tolist())
    snap_df = snap_df[snap_df["satellite_name"].isin(available_names)].copy()
    snap_df = snap_df.sort_values("elevation_deg", ascending=False).reset_index(drop=True)

    visible_snap_df = snap_df[snap_df["elevation_deg"] >= elev_visible].copy()
    n_visible_ts = len(visible_snap_df)

    beam_rows_ts = []

    for _, sat_row in visible_snap_df.iterrows():
        sat_match = snap_sat_df[snap_sat_df["name"] == sat_row["satellite_name"]]
        if sat_match.empty:
            continue

        sat_lat = float(sat_match.iloc[0]["lat"])
        sat_lon = float(sat_match.iloc[0]["lon"])

        beams = generate_beam_codebook(
            sat_lat=sat_lat,
            sat_lon=sat_lon,
            terminal_lat=terminal_lat,
            terminal_lon=terminal_lon,
            sat_elevation_deg=float(sat_row["elevation_deg"]),
        )

        evaluated_beams = evaluate_terminal_against_beams(
            terminal_lat=terminal_lat,
            terminal_lon=terminal_lon,
            sat_name=sat_row["satellite_name"],
            sat_elevation_deg=float(sat_row["elevation_deg"]),
            sat_range_km=float(sat_row["range_km"]),
            beams=beams,
            rf_params=rf_params,
        )
        beam_rows_ts.extend(evaluated_beams)

    beam_df_ts = pd.DataFrame(beam_rows_ts)

    if not beam_df_ts.empty:
        serviceable_beam_df_ts = beam_df_ts[
            (beam_df_ts["inside_beam"]) & (beam_df_ts["sinr_db"] >= rf_params["sinr_service_threshold_db"])
        ].copy()
    else:
        serviceable_beam_df_ts = pd.DataFrame()

    n_serviceable_ts = (
        serviceable_beam_df_ts["satellite_name"].nunique()
        if not serviceable_beam_df_ts.empty
        else 0
    )

    if n_visible_ts == 0:
        outage_flag = True
        outage_type_ts = "Visibility outage"
        outage_reason_ts = "No satellites above visible threshold"
    elif n_serviceable_ts == 0:
        outage_flag = True
        outage_type_ts = "Beam/service outage"
        outage_reason_ts = "Satellites are visible, but no beam meets the SINR service threshold"
    else:
        outage_flag = False
        outage_type_ts = "None"
        outage_reason_ts = "Service available"

    timeline_rows.append(
        {
            "timestamp_utc": pd.Timestamp(ts),
            "visible_sat_count": n_visible_ts,
            "serviceable_sat_count": n_serviceable_ts,
            "outage": outage_flag,
            "outage_type": outage_type_ts,
            "outage_reason": outage_reason_ts,
        }
    )

coverage_timeline_df = pd.DataFrame(timeline_rows)

if "frame_idx" not in st.session_state:
    st.session_state.frame_idx = 0

if "selected_time_manual" not in st.session_state:
    st.session_state.selected_time_manual = all_times[0]

if st.sidebar.button("Reset animation"):
    st.session_state.frame_idx = 0
    st.session_state.selected_time_manual = all_times[0]

auto_play = st.sidebar.checkbox("Auto-play animation", value=False)
loop_animation = st.sidebar.checkbox("Loop animation", value=True)
playback_delay_ms = st.sidebar.slider("Playback delay (ms)", 100, 2000, 500, 100)
frame_step = st.sidebar.slider("Animation frame jump", 1, 10, 4, 1)

# keep frame index valid
if st.session_state.frame_idx >= len(all_times):
    st.session_state.frame_idx = len(all_times) - 1

if auto_play:
    selected_time = all_times[st.session_state.frame_idx]
    st.sidebar.caption(
        f"Simulation time: {pd.Timestamp(selected_time).strftime('%Y-%m-%d %H:%M:%S')}"
    )
else:
    selected_time = st.sidebar.select_slider(
        "Simulation time",
        options=all_times,
        value=st.session_state.selected_time_manual,
        format_func=lambda x: pd.Timestamp(x).strftime("%Y-%m-%d %H:%M:%S"),
    )
    st.session_state.selected_time_manual = selected_time
    st.session_state.frame_idx = all_times.index(selected_time)

current_df = df[df["timestamp_utc"] == pd.Timestamp(selected_time)].copy()
sat_df = build_satellite_points(str(scenario_file), str(selected_time), max_sats)

available_names = set(sat_df["name"].tolist())
current_df = current_df[current_df["satellite_name"].isin(available_names)].copy()
current_df = current_df.sort_values("elevation_deg", ascending=False).reset_index(drop=True)

visible_df = current_df[current_df["elevation_deg"] >= elev_visible].copy()

beam_rows = []
terminal_lat = config["region"]["latitude_deg"]
terminal_lon = config["region"]["longitude_deg"]

for _, sat_row in visible_df.iterrows():
    sat_match = sat_df[sat_df["name"] == sat_row["satellite_name"]]
    if sat_match.empty:
        continue

    sat_lat = float(sat_match.iloc[0]["lat"])
    sat_lon = float(sat_match.iloc[0]["lon"])

    beams = generate_beam_codebook(
        sat_lat=sat_lat,
        sat_lon=sat_lon,
        terminal_lat=terminal_lat,
        terminal_lon=terminal_lon,
        sat_elevation_deg=float(sat_row["elevation_deg"]),
    )

    evaluated_beams = evaluate_terminal_against_beams(
        terminal_lat=terminal_lat,
        terminal_lon=terminal_lon,
        sat_name=sat_row["satellite_name"],
        sat_elevation_deg=float(sat_row["elevation_deg"]),
        sat_range_km=float(sat_row["range_km"]),
        beams=beams,
        rf_params=rf_params,
    )
    beam_rows.extend(evaluated_beams)

beam_df = pd.DataFrame(beam_rows)

required_beam_cols = {
    "satellite_name",
    "beam_id",
    "inside_beam",
    "beam_score",
    "beam_lat",
    "beam_lon",
    "beam_radius_km",
}

if beam_df.empty or not required_beam_cols.issubset(set(beam_df.columns)):
    serviceable_beam_df = pd.DataFrame(
        columns=[
            "satellite_name",
            "beam_id",
            "beam_score",
            "inside_beam",
            "beam_lat",
            "beam_lon",
            "beam_radius_km",
        ]
    )
else:
    serviceable_beam_df = beam_df[
        (beam_df["inside_beam"]) & (beam_df["sinr_db"] >= rf_params["sinr_service_threshold_db"])
    ].copy()
    serviceable_beam_df = serviceable_beam_df.sort_values(
        "sinr_db",
        ascending=False,
    ).reset_index(drop=True)

#st.write("DEBUG beam_rows count:", len(beam_rows))
#
# st.write("DEBUG beam_df columns:", list(beam_df.columns))

n_visible = len(visible_df)
n_serviceable = serviceable_beam_df["satellite_name"].nunique() if not serviceable_beam_df.empty else 0

serving_sat = None
serving_beam_id = None
candidate_df = pd.DataFrame()

if not serviceable_beam_df.empty:
    serving_sat = serviceable_beam_df.iloc[0]["satellite_name"]
    serving_beam_id = serviceable_beam_df.iloc[0]["beam_id"]

    candidate_df = (
        serviceable_beam_df.iloc[1:4][["satellite_name", "beam_id", "beam_score", "sinr_db"]]
        .copy()
        .reset_index(drop=True)
    )

outage_now = False
outage_type = "None"
outage_reason = "Service available"

if n_visible == 0:
    outage_now = True
    outage_type = "Visibility outage"
    outage_reason = "No satellites above visible threshold"
elif n_serviceable == 0:
    outage_now = True
    outage_type = "Beam/service outage"
    outage_reason = "Satellites are visible, but no beam meets the SINR service threshold"

imminent_outage = False
imminent_reason = "No immediate outage risk detected"

selected_idx = None
for i, ts in enumerate(coverage_timeline_df["timestamp_utc"]):
    if pd.Timestamp(ts) == pd.Timestamp(selected_time):
        selected_idx = i
        break

if selected_idx is not None:
    future_df = coverage_timeline_df.iloc[
        selected_idx + 1 : selected_idx + 1 + prediction_horizon_steps
    ].copy()

    if serving_sat is not None and not future_df.empty:
        if (future_df["serviceable_sat_count"] == 0).any():
            imminent_outage = True
            imminent_reason = (
                "Serving satellite expected to drop below service threshold and "
                "no serviceable backup candidate detected in look-ahead window"
            )

sat_df["role"] = "non_visible"
sat_df.loc[sat_df["name"].isin(visible_df["satellite_name"]), "role"] = "visible"

if serving_sat is not None:
    sat_df.loc[sat_df["name"] == serving_sat, "role"] = "serving"

if not candidate_df.empty:
    sat_df.loc[sat_df["name"].isin(candidate_df["satellite_name"]), "role"] = "candidate"


def role_color(role: str):
    if role == "serving":
        return [0, 255, 120, 220]
    if role == "candidate":
        return [255, 200, 0, 220]
    if role == "visible":
        return [0, 180, 255, 200]
    return [40, 40, 40, 200]


sat_df["color"] = sat_df["role"].apply(role_color)
sat_df["radius"] = sat_df["role"].map(
    {
        "serving": 50000,
        "candidate": 40000,
        "visible": 30000,
        "non_visible": 22000,
    }
)
sat_df["elevation"] = sat_df["alt_m"]

coverage_rows = []

if not beam_df.empty:
    beam_map_df = beam_df[beam_df["inside_beam"] == True].copy()
    beam_map_df["beam_role"] = "non_serving_beam"

    if serving_sat is not None and serving_beam_id is not None:
        beam_map_df.loc[
            (beam_map_df["satellite_name"] == serving_sat) &
            (beam_map_df["beam_id"] == serving_beam_id),
            "beam_role"
        ] = "serving_beam"

    if not candidate_df.empty:
        for _, cand_row in candidate_df.iterrows():
            beam_map_df.loc[
                (beam_map_df["satellite_name"] == cand_row["satellite_name"]) &
                (beam_map_df["beam_id"] == cand_row["beam_id"]),
                "beam_role"
            ] = "candidate_beam"

    beam_map_df = beam_map_df[
        beam_map_df["beam_role"].isin(["serving_beam", "candidate_beam"])
    ].copy()

    def beam_fill_color(role):
        if role == "serving_beam":
            return [0, 255, 120, 90]
        if role == "candidate_beam":
            return [255, 255, 0, 20]
        return [0, 180, 255, 8]

    def beam_line_color(role):
        if role == "serving_beam":
            return [0, 180, 90, 220]
        if role == "candidate_beam":
            return [255, 180, 0, 220]
        return [0, 120, 255, 120]

    beam_map_df["fill_color"] = beam_map_df["beam_role"].apply(beam_fill_color)
    beam_map_df["line_color"] = beam_map_df["beam_role"].apply(beam_line_color)

    for _, row in beam_map_df.iterrows():
        coverage_rows.append(
            {
                "name": f"{row['satellite_name']} | {row['beam_id']}",
                "satellite": row["satellite_name"],
                "beam_id": row["beam_id"],
                "sinr_db": row["sinr_db"],
                "rx_power_dbw": row["rx_power_dbw"],
                "fspl_db": row["fspl_db"],
                "beam_gain_rel_db": row["beam_gain_rel_db"],
                "polygon": hex_polygon(
                    row["beam_lat"],
                    row["beam_lon"],
                    row["beam_radius_km"],
                ),
                "fill_color": row["fill_color"],
                "line_color": row["line_color"],
            }
        )

coverage_df = pd.DataFrame(coverage_rows)

if not beam_df.empty:
    beam_center_df = beam_df.copy()

    beam_center_df["beam_role"] = "other_beam"

    if serving_sat is not None and serving_beam_id is not None:
        beam_center_df.loc[
            (beam_center_df["satellite_name"] == serving_sat) &
            (beam_center_df["beam_id"] == serving_beam_id),
            "beam_role"
        ] = "serving_beam"

    if not candidate_df.empty:
        for _, cand_row in candidate_df.iterrows():
            beam_center_df.loc[
                (beam_center_df["satellite_name"] == cand_row["satellite_name"]) &
                (beam_center_df["beam_id"] == cand_row["beam_id"]),
                "beam_role"
            ] = "candidate_beam"

    beam_center_df = beam_center_df[beam_center_df["inside_beam"] == True].copy()

    # Keep only serving + candidate beam centers
    beam_center_df = beam_center_df[
        beam_center_df["beam_role"].isin(["serving_beam", "candidate_beam"])
    ].copy()

    def beam_center_color(role: str):
        if role == "serving_beam":
            return [0, 255, 120, 230]
        return [255, 200, 0, 230]

    beam_center_df["center_color"] = beam_center_df["beam_role"].apply(beam_center_color)
    beam_center_df["center_radius"] = beam_center_df["beam_role"].map(
        {
            "serving_beam": 24000,
            "candidate_beam": 18000,
        }
    )

    beam_center_df["name"] = (
        beam_center_df["satellite_name"] + " | " + beam_center_df["beam_id"]
    )

else:
    beam_center_df = pd.DataFrame(
        columns=["beam_lat", "beam_lon", "center_color", "center_radius", "name"]
    )

region = config["region"]

observer_df = pd.DataFrame(
    [
        {
            "name": region["name"],
            "lat": region["latitude_deg"],
            "lon": region["longitude_deg"],
            "alt_m": 0,
            "size": 80000,
        }
    ]
)

line_rows = []

user_lon = region["longitude_deg"]
user_lat = region["latitude_deg"]

if serving_sat is not None:
    serving_rows = sat_df[sat_df["name"] == serving_sat]
    if not serving_rows.empty:
        sat_row = serving_rows.iloc[0]
        line_rows.append(
            {
                "path": [
                    [user_lon, user_lat],
                    [sat_row["lon"], sat_row["lat"]],
                ],
                "color": [0, 255, 120],
                "width": 5,
                "name": f"user_to_{serving_sat}",
            }
        )

line_df = pd.DataFrame(line_rows)

left, right = st.columns([1.2, 1])

with left:
    st.subheader("Quebec / Arctic connectivity map")
    st.markdown("### Map legend")

    st.caption(
        "Beam families: "
        "S0 = terminal-steered center beam · "
        "S1_i = inner ring steered beams · "
        "S2_i = outer ring steered beams · "
        "F0 = fallback beam near satellite subpoint"
    )

    legend_col1, legend_col2 = st.columns(2)

    with legend_col1:
        st.markdown(
            """
            <div style="line-height:1.9">
                <span style="display:inline-block;width:14px;height:14px;background-color:rgb(255,140,0);border-radius:50%;margin-right:8px;"></span>
                <b>User terminal</b><br>
                <span style="display:inline-block;width:14px;height:14px;background-color:rgb(0,255,120);border-radius:50%;margin-right:8px;"></span>
                <b>Serving satellite</b><br>
                <span style="display:inline-block;width:14px;height:14px;background-color:rgb(255,200,0);border-radius:50%;margin-right:8px;"></span>
                <b>Candidate satellite</b><br>
                <span style="display:inline-block;width:14px;height:14px;background-color:rgb(0,180,255);border-radius:50%;margin-right:8px;"></span>
                <b>Visible satellite</b>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with legend_col2:
        st.markdown(
            """
            <div style="line-height:1.9">
                <span style="display:inline-block;width:22px;height:4px;background-color:rgb(0,255,120);margin-right:8px;vertical-align:middle;"></span>
                <b>Serving link</b><br>
                <span style="display:inline-block;width:22px;height:4px;background-color:rgb(255,200,0);margin-right:8px;vertical-align:middle;"></span>
                <b>Candidate link</b><br>
                <span style="display:inline-block;width:18px;height:18px;background-color:rgba(0,255,120,0.25);border:1px solid #999;margin-right:8px;vertical-align:middle;"></span>
                <b>Coverage polygon</b>
            </div>
            """,
            unsafe_allow_html=True,
        )

    layer_coverage = pdk.Layer(
        "PolygonLayer",
        data=coverage_df,
        get_polygon="polygon",
        get_fill_color="fill_color",
        get_line_color="line_color",
        stroked=True,
        filled=True,
        line_width_min_pixels=2,
        pickable=True,
    )

    layer_lines = pdk.Layer(
        "PathLayer",
        data=line_df,
        get_path="path",
        get_color="color",
        get_width="width",
        width_scale=1,
        width_min_pixels=2,
        pickable=True,
    )

    layer_sat = pdk.Layer(
        "ScatterplotLayer",
        data=sat_df,
        get_position='[lon, lat]',
        get_radius='radius',
        get_fill_color='color',
        pickable=True,
    )

    layer_observer = pdk.Layer(
        "ScatterplotLayer",
        data=observer_df,
        get_position='[lon, lat]',
        get_radius='size',
        get_fill_color='[255, 140, 0, 220]',
        pickable=True,
    )

    layer_beam_centers = pdk.Layer(
        "ScatterplotLayer",
        data=beam_center_df,
        get_position='[beam_lon, beam_lat]',
        get_radius='center_radius',
        get_fill_color='center_color',
        pickable=True,
    )

    view_state = pdk.ViewState(
        latitude=58.0,
        longitude=-72.0,
        zoom=3.5,
        pitch=0,
    )

    deck = pdk.Deck(
        layers=[layer_coverage, layer_beam_centers, layer_lines, layer_sat, layer_observer],
        initial_view_state=view_state,
        tooltip={"text": "{name}"},
        map_style="light",
    )

    st.pydeck_chart(deck)

with right:
    st.subheader("Link state")
    st.caption(
        "Serving = highest SINR beam with terminal inside active footprint · "
        "Candidates = next best SINR options · "
        "Visible = all satellites above visible threshold"
    )

    st.caption(f"SINR service threshold: {rf_params['sinr_service_threshold_db']} dB")

    st.metric("Serving satellite", serving_sat if serving_sat else "None")
    st.metric("Serving beam", serving_beam_id if serving_beam_id else "None")
    st.metric("Candidate satellites", len(candidate_df))
    st.metric("Visible satellites", n_visible)
    st.metric("Serviceable satellites", n_serviceable)

    st.subheader("Outage status")
    st.write(f"**Outage now:** {'Yes' if outage_now else 'No'}")
    st.write(f"**Outage type:** {outage_type}")
    st.write(f"**Reason:** {outage_reason}")

    st.subheader("Imminent outage prediction")
    st.write(f"**Imminent outage:** {'Yes' if imminent_outage else 'No'}")
    st.write(f"**Reason:** {imminent_reason}")

    st.subheader("Visible satellites now")
    visible_table_df = visible_df[
        ["satellite_name", "elevation_deg", "azimuth_deg", "range_km"]
    ].copy()

    if not serviceable_beam_df.empty:
        best_beam_per_sat = (
            serviceable_beam_df.sort_values("sinr_db", ascending=False)
            .drop_duplicates(subset=["satellite_name"])
            [[
                "satellite_name",
                "beam_id",
                "beam_tier",
                "beam_radius_km",
                "off_axis_ratio",
                "gain_like",
                "beam_score",
                "beam_gain_rel_db",
                "fspl_db",
                "rx_power_dbw",
                "noise_power_dbw",
                "sinr_db",
            ]]
        )

        visible_table_df = visible_table_df.merge(
            best_beam_per_sat,
            on="satellite_name",
            how="left",
        )

    if "sinr_db" in visible_table_df.columns:
        sort_col = "sinr_db"
    elif "beam_score" in visible_table_df.columns:
        sort_col = "beam_score"
    else:
        sort_col = "elevation_deg"

    st.dataframe(
        visible_table_df.sort_values(sort_col, ascending=False).reset_index(drop=True),
        use_container_width=True,
    )

st.subheader("Elevation pass timeline")
plot_df = (
    df.sort_values(["satellite_name", "timestamp_utc"])
    .groupby("satellite_name")
    .head(30)
    .copy()
)

pass_fig = px.line(
    plot_df,
    x="timestamp_utc",
    y="elevation_deg",
    color="satellite_name",
    title=f"Elevation vs time — {region['name']}",
    labels={"timestamp_utc": "UTC time", "elevation_deg": "Elevation (deg)"},
)
st.plotly_chart(pass_fig, use_container_width=True)

# --- Run Sammary ---
st.subheader("Run summary")
col1, col2, col3 = st.columns(3)
col1.metric("Visible samples", len(df))
col2.metric("Unique visible satellites", df["satellite_name"].nunique())
col3.metric("Current visible satellites", len(visible_df))

# --- Compute window duration ---
total_window_s = 0
if len(coverage_timeline_df) >= 2:
    step_seconds_actual = (
        pd.Timestamp(coverage_timeline_df.iloc[1]["timestamp_utc"]) -
        pd.Timestamp(coverage_timeline_df.iloc[0]["timestamp_utc"])
    ).total_seconds()
    total_window_s = int(step_seconds_actual * (len(coverage_timeline_df) - 1))
else:
    total_window_s = forecast_duration_min * 60 if time_mode == "Forecast from now" else 0

# --- Compute outage duration ---
total_outage_s = 0
temp_outage_intervals = []
in_outage_tmp = False
start_time_tmp = None

for _, row in coverage_timeline_df.iterrows():
    ts = row["timestamp_utc"]
    outage = row["outage"]

    if outage and not in_outage_tmp:
        in_outage_tmp = True
        start_time_tmp = ts

    elif not outage and in_outage_tmp:
        temp_outage_intervals.append((start_time_tmp, ts))
        in_outage_tmp = False
        start_time_tmp = None

if in_outage_tmp:
    temp_outage_intervals.append(
        (
            start_time_tmp,
            coverage_timeline_df.iloc[-1]["timestamp_utc"],
        )
    )

for start_ts, end_ts in temp_outage_intervals:
    total_outage_s += int((pd.Timestamp(end_ts) - pd.Timestamp(start_ts)).total_seconds())

# --- Availability metric ---
availability_pct = 100.0
if total_window_s > 0:
    availability_pct = max(0.0, 100.0 * (total_window_s - total_outage_s) / total_window_s)

# --- Dashboard gauge ---
st.subheader("Link availability gauge")

g1, g2, g3 = st.columns(3)
g1.metric("Availability", f"{availability_pct:.1f}%")
g2.metric("Total outage", f"{total_outage_s} s")
g3.metric("Window", f"{total_window_s} s")

if availability_pct >= 99.0:
    st.success("Availability status: Excellent")
elif availability_pct >= 95.0:
    st.info("Availability status: Good")
elif availability_pct >= 90.0:
    st.warning("Availability status: Moderate")
else:
    st.error("Availability status: Poor")

st.subheader("Coverage outage intervals")

outage_intervals = []
in_outage = False
start_time = None
start_type = None
start_reason = None

for _, row in coverage_timeline_df.iterrows():
    ts = row["timestamp_utc"]
    outage = row["outage"]

    if outage and not in_outage:
        in_outage = True
        start_time = ts
        start_type = row["outage_type"]
        start_reason = row["outage_reason"]
    elif not outage and in_outage:
        outage_intervals.append((start_time, ts, start_type, start_reason))
        in_outage = False
        start_time = None
        start_type = None
        start_reason = None

if in_outage:
    outage_intervals.append(
        (
            start_time,
            coverage_timeline_df.iloc[-1]["timestamp_utc"],
            start_type,
            start_reason,
        )
    )

if not outage_intervals:
    st.success("No outage intervals found in this simulation window.")
else:
    interval_rows = []
    for start_ts, end_ts, outage_type_i, outage_reason_i in outage_intervals:
        duration_s = (pd.Timestamp(end_ts) - pd.Timestamp(start_ts)).total_seconds()
        interval_rows.append(
            {
                "outage_start": start_ts,
                "outage_end": end_ts,
                "duration_s": int(duration_s),
                "outage_type": outage_type_i,
                "reason": outage_reason_i,
            }
        )

    outage_interval_df = pd.DataFrame(interval_rows)
    st.dataframe(outage_interval_df, use_container_width=True)

if auto_play:
    import time

    time.sleep(playback_delay_ms / 1000.0)

    next_idx = st.session_state.frame_idx + frame_step

    if next_idx < len(all_times):
        st.session_state.frame_idx = next_idx
    elif loop_animation:
        st.session_state.frame_idx = 0
    else:
        st.session_state.frame_idx = len(all_times) - 1

    st.rerun()