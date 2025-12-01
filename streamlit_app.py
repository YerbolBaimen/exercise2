import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# -----------------------------------------------------------
# Page setup
# -----------------------------------------------------------
st.set_page_config(
    page_title="Law Enforcement Crime Dashboard",
    layout="wide",
)

st.title("🚔 Law Enforcement Crime Dashboard")

st.markdown(
    "Upload the Boston **crime.csv** data file to explore crime trends, "
    "summary metrics, and district-level patterns."
)

# -----------------------------------------------------------
# Sidebar – controls & file upload
# -----------------------------------------------------------
st.sidebar.header("📊 Controls")

uploaded_file = st.sidebar.file_uploader(
    "Choose Boston crime CSV file",
    type=["csv"],
    help="Upload the Boston crime dataset (crime.csv)."
)

@st.cache_data
def load_data(file):
    df = pd.read_csv(file, parse_dates=["OCCURRED_ON_DATE"])
    df = df.dropna(subset=["OCCURRED_ON_DATE"])
    return df

if uploaded_file is None:
    st.info("⬅️ Please upload **crime.csv** in the sidebar to begin.")
    st.stop()

df = load_data(uploaded_file)

# -----------------------------------------------------------
# Filters
# -----------------------------------------------------------
# Date range
min_date = df["OCCURRED_ON_DATE"].dt.date.min()
max_date = df["OCCURRED_ON_DATE"].dt.date.max()

date_range = st.sidebar.date_input(
    "Select date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

if isinstance(date_range, tuple):
    start_date, end_date = date_range
else:  # single date chosen – treat as both start and end
    start_date = end_date = date_range

# District filter
districts = sorted(df["DISTRICT"].dropna().unique().tolist())
selected_districts = st.sidebar.multiselect(
    "Filter by district (optional)",
    options=districts,
    default=districts,
)

# Apply filters
mask = (
    (df["OCCURRED_ON_DATE"].dt.date >= start_date)
    & (df["OCCURRED_ON_DATE"].dt.date <= end_date)
)

if selected_districts:
    mask &= df["DISTRICT"].isin(selected_districts)

filtered = df.loc[mask].copy()

st.sidebar.markdown(
    f"**Showing {len(filtered):,} records** "
    f"from {start_date} to {end_date}"
)

if filtered.empty:
    st.warning("No data for the selected filters. Try broadening the date or districts.")
    st.stop()

# -----------------------------------------------------------
# Summary statistics (KPIs)
# -----------------------------------------------------------
ucr_part_one = filtered.loc[filtered["UCR_PART"] == "Part One"]
ucr_part_two = filtered.loc[filtered["UCR_PART"] == "Part Two"]
shootings = filtered.loc[filtered["SHOOTING"].notna() & (filtered["SHOOTING"] != "")]

col1, col2, col3 = st.columns(3)

col1.metric("UCR Part One Offenses", f"{len(ucr_part_one):,}")
col2.metric("UCR Part Two Offenses", f"{len(ucr_part_two):,}")
col3.metric("Shooting Incidents", f"{len(shootings):,}")

st.markdown("---")

# -----------------------------------------------------------
# Daily crime trends with 7-day rolling average
# -----------------------------------------------------------
st.subheader("📈 Daily Crime Volume (with 7-Day Rolling Average)")

daily_counts = (
    filtered
    .set_index("OCCURRED_ON_DATE")
    .resample("D")
    .size()
    .rename("count")
    .to_frame()
)

daily_counts["rolling_7d"] = daily_counts["count"].rolling(window=7, min_periods=1).mean()

daily_long = (
    daily_counts
    .reset_index()
    .melt(id_vars="OCCURRED_ON_DATE",
          value_vars=["count", "rolling_7d"],
          var_name="Series",
          value_name="Incidents")
)

fig_daily = px.line(
    daily_long,
    x="OCCURRED_ON_DATE",
    y="Incidents",
    color="Series",
    labels={
        "OCCURRED_ON_DATE": "Date",
        "Incidents": "Number of Incidents",
        "Series": ""
    },
)
fig_daily.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))

st.plotly_chart(fig_daily, use_container_width=True)

# -----------------------------------------------------------
# Crimes by district – bar chart
# -----------------------------------------------------------
st.subheader("🏙️ Crimes by District")

district_counts = (
    filtered
    .groupby("DISTRICT", dropna=False)
    .size()
    .reset_index(name="Count")
    .sort_values("Count", ascending=False)
)

district_counts["DISTRICT"].fillna("Unknown", inplace=True)

fig_district = px.bar(
    district_counts,
    x="Count",
    y="DISTRICT",
    orientation="h",
    labels={"DISTRICT": "District", "Count": "Number of Incidents"},
)
st.plotly_chart(fig_district, use_container_width=True)

# -----------------------------------------------------------
# Top 10 offense types – pie chart
# -----------------------------------------------------------
st.subheader("🔟 Top 10 Offense Code Groups")

offense_counts = (
    filtered
    .groupby("OFFENSE_CODE_GROUP")
    .size()
    .reset_index(name="Count")
    .sort_values("Count", ascending=False)
    .head(10)
)

fig_offense = px.pie(
    offense_counts,
    names="OFFENSE_CODE_GROUP",
    values="Count",
    hole=0.3,
)
st.plotly_chart(fig_offense, use_container_width=True)

# -----------------------------------------------------------
# Optional: Map of incidents (subset for performance)
# -----------------------------------------------------------
st.subheader("🗺️ Locations of Incidents (sample)")

map_data = filtered.dropna(subset=["Lat", "Long"]).copy()
if len(map_data) > 5000:
    map_data = map_data.sample(5000, random_state=42)

if map_data.empty:
    st.info("No geocoded incidents available for the selected filters.")
else:
    fig_map = px.scatter_mapbox(
        map_data,
        lat="Lat",
        lon="Long",
        hover_name="OFFENSE_CODE_GROUP",
        hover_data=["DISTRICT", "OCCURRED_ON_DATE"],
        zoom=10,
        height=400,
    )
    fig_map.update_layout(mapbox_style="open-street-map")
    fig_map.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig_map, use_container_width=True)
