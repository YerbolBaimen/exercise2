import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import altair as alt

# -----------------------------------------------------------
# Page setup
# -----------------------------------------------------------
st.set_page_config(
    page_title="Law Enforcement Crime Dashboard",
    layout="wide",
)

st.title("🚔 Law Enforcement Crime Dashboard")

st.markdown("Upload **Boston crime data CSV** to generate insights, KPIs, and district patterns.")

# -----------------------------------------------------------
# Sidebar – controls & file upload
# -----------------------------------------------------------
st.sidebar.header("📊 Controls")

uploaded_file = st.sidebar.file_uploader("Upload Boston Crimes CSV", type=["csv"])

@st.cache_data
def load_data(file):
    df = pd.read_csv(file, parse_dates=["OCCURRED_ON_DATE"])
    df = df.dropna(subset=["OCCURRED_ON_DATE"])
    return df

if uploaded_file is None:
    st.info("⬅️ Please upload **crime.csv** to start.")
    st.stop()

df = load_data(uploaded_file)

# -----------------------------------------------------------
# Filters
# -----------------------------------------------------------
min_date = df["OCCURRED_ON_DATE"].dt.date.min()
max_date = df["OCCURRED_ON_DATE"].dt.date.max()

date_range = st.sidebar.date_input(
    "Select date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

# handle single-date selection
if isinstance(date_range, tuple):
    start_date, end_date = date_range
else:
    start_date = end_date = date_range

# District filter
districts = sorted(df["DISTRICT"].dropna().unique().tolist())
selected_districts = st.sidebar.multiselect(
    "Filter by district",
    options=districts,
    default=districts,
)

# UCR Part filter
ucr_filter = st.sidebar.radio(
    "Filter by UCR Part",
    options=["All", "Part One only", "Part Two only"],
    index=0,
)

# Shooting filter
shooting_filter = st.sidebar.radio(
    "Filter by shooting",
    options=["All", "Shooting only", "Non-shooting only"],
    index=0,
)

# Base mask: date range
mask = (df["OCCURRED_ON_DATE"].dt.date >= start_date) & \
       (df["OCCURRED_ON_DATE"].dt.date <= end_date)

# District mask
if selected_districts:
    mask &= df["DISTRICT"].isin(selected_districts)

# UCR Part mask
if ucr_filter == "Part One only":
    mask &= df["UCR_PART"] == "Part One"
elif ucr_filter == "Part Two only":
    mask &= df["UCR_PART"] == "Part Two"

# Shooting mask
if shooting_filter == "Shooting only":
    mask &= df["SHOOTING"].notna() & (df["SHOOTING"] != "")
elif shooting_filter == "Non-shooting only":
    mask &= df["SHOOTING"].isna() | (df["SHOOTING"] == "")

filtered = df.loc[mask].copy()

st.sidebar.write(f"**Showing {len(filtered):,} records**")

if filtered.empty:
    st.warning("No data available for selected filters.")
    st.stop()

# -----------------------------------------------------------
# KPI metric cards (no headline summary text line)
# -----------------------------------------------------------
total_offenses = len(filtered)
ucr_part_one = filtered.loc[filtered["UCR_PART"] == "Part One"]
ucr_part_two = filtered.loc[filtered["UCR_PART"] == "Part Two"]
shootings = filtered.loc[filtered["SHOOTING"].notna() & (filtered["SHOOTING"] != "")]

c0, c1, c2, c3 = st.columns(4)
c0.metric("Total Offenses", total_offenses)
c1.metric("UCR Part One Offenses", len(ucr_part_one))
c2.metric("UCR Part Two Offenses", len(ucr_part_two))
c3.metric("Shooting Incidents", len(shootings))

st.markdown("---")

# -----------------------------------------------------------
# 1) Daily crime trend with 7-day rolling avg
# -----------------------------------------------------------
st.subheader("📈 Daily Crime Volume (7-Day Rolling Average)")

daily_counts = (
    filtered
    .set_index("OCCURRED_ON_DATE")
    .resample("D")
    .size()
    .to_frame(name="count")
)
daily_counts["rolling_7d"] = daily_counts["count"].rolling(window=7, min_periods=1).mean()

st.line_chart(daily_counts)

# -----------------------------------------------------------
# 2) Crimes by district – bar chart (alphabetical order)
# -----------------------------------------------------------
st.subheader("🏙️ Crimes by District")

dist_counts = (
    filtered
    .groupby("DISTRICT")
    .size()
    .to_frame(name="Count")
)

# Sort districts alphabetically by index
dist_counts = dist_counts.sort_index()

st.bar_chart(dist_counts)

# -----------------------------------------------------------
# 3) Offense groups – PIE CHART (top 10 + Others) with Altair
# -----------------------------------------------------------
st.subheader("🔍 Offense Groups (Top 10 + Others)")

offense_counts_full = (
    filtered
    .groupby("OFFENSE_CODE_GROUP")
    .size()
    .reset_index(name="count")
    .sort_values("count", ascending=False)
)

if offense_counts_full.empty:
    st.info("No offense data available for the selected filters.")
else:
    # Top 10
    top10 = offense_counts_full.head(10).copy()
    top10_total = top10["count"].sum()
    overall_total = offense_counts_full["count"].sum()
    others_count = overall_total - top10_total

    if others_count > 0:
        others_row = pd.DataFrame(
            [{"OFFENSE_CODE_GROUP": "Others", "count": others_count}]
        )
        pie_data = pd.concat([top10, others_row], ignore_index=True)
    else:
        pie_data = top10

    # Ensure string labels and sort by count
    pie_data["OFFENSE_CODE_GROUP"] = pie_data["OFFENSE_CODE_GROUP"].astype(str)
    pie_data = pie_data.sort_values("count", ascending=False)

    pie_chart = (
        alt.Chart(pie_data)
        .mark_arc()
        .encode(
            theta=alt.Theta(field="count", type="quantitative"),
            color=alt.Color(field="OFFENSE_CODE_GROUP", type="nominal",
                            legend=alt.Legend(title="Offense Group")),
            tooltip=["OFFENSE_CODE_GROUP", "count"],
        )
        .properties(width=400, height=400)
    )

    st.altair_chart(pie_chart, use_container_width=True)

# -----------------------------------------------------------
# 4) Incident map – centered on Boston, district-colored
# -----------------------------------------------------------
st.subheader("🗺 Location of Crime Incidents (colored by district)")

geo = filtered.dropna(subset=["Lat", "Long"]).copy()

# sample for performance
if len(geo) > 4000:
    geo = geo.sample(4000, random_state=42)

if geo.empty:
    st.info("No geocoded incidents available for the selected filters.")
else:
    # build a color map for districts
    unique_districts = sorted(geo["DISTRICT"].dropna().unique())
    color_palette = [
        [230, 25, 75],   # red
        [60, 180, 75],   # green
        [0, 130, 200],   # blue
        [245, 130, 48],  # orange
        [145, 30, 180],  # purple
        [70, 240, 240],  # cyan
        [240, 50, 230],  # magenta
        [210, 245, 60],  # lime
        [250, 190, 190], # pink
        [0, 128, 128],   # teal
        [170, 110, 40],  # brown
        [128, 128, 0],   # olive
        [0, 0, 128],     # navy
    ]
    color_map = {
        d: color_palette[i % len(color_palette)]
        for i, d in enumerate(unique_districts)
    }

    # assign colors (fallback gray for NaN)
    geo["color"] = geo["DISTRICT"].map(color_map)
    geo["color"] = geo["color"].apply(
        lambda c: c if isinstance(c, list) else [200, 200, 200]
    )

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=geo,
        get_position=["Long", "Lat"],
        get_radius=40,
        get_fill_color="color",
        pickable=True,
        auto_highlight=True,
    )

    # Centered on Boston
    view_state = pdk.ViewState(
        latitude=42.3601,
        longitude=-71.0589,
        zoom=11,
        pitch=0,
        bearing=0,
    )

    tooltip = {
        "text": "District: {DISTRICT}\nOffense: {OFFENSE_CODE_GROUP}\nDate: {OCCURRED_ON_DATE}"
    }

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
    )

    st.pydeck_chart(deck, use_container_width=True)
