import streamlit as st
import pandas as pd
import numpy as np

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

uploaded_file = st.sidebar.file_uploader("Upload Boston Crimses CSV", type=["csv"])

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

date_range = st.sidebar.date_input("Select date range", value=(min_date, max_date), min_value=min_date, max_value=max_date)

start_date, end_date = date_range

districts = sorted(df["DISTRICT"].dropna().unique().tolist())
selected_districts = st.sidebar.multiselect("Filter by district", options=districts, default=districts)

mask = (df["OCCURRED_ON_DATE"].dt.date >= start_date) & (df["OCCURRED_ON_DATE"].dt.date <= end_date)
mask &= df["DISTRICT"].isin(selected_districts)

filtered = df.loc[mask].copy()

st.sidebar.write(f"**Showing {len(filtered):,} records**")

if filtered.empty:
    st.warning("No data available for selected filters.")
    st.stop()

# -----------------------------------------------------------
# KPIs
# -----------------------------------------------------------
ucr_part_one = filtered.loc[filtered["UCR_PART"] == "Part One"]
ucr_part_two = filtered.loc[filtered["UCR_PART"] == "Part Two"]
shootings = filtered.loc[filtered["SHOOTING"].notna() & (filtered["SHOOTING"] != "")]

c1, c2, c3 = st.columns(3)
c1.metric("UCR Part One Offenses", len(ucr_part_one))
c2.metric("UCR Part Two Offenses", len(ucr_part_two))
c3.metric("Shooting Incidents", len(shootings))

st.markdown("---")

# -----------------------------------------------------------
# 1) Daily crime trend with 7-day rolling avg
# -----------------------------------------------------------
st.subheader("📈 Daily Crime Volume (7-Day Rolling Average)")

daily_counts = filtered.set_index("OCCURRED_ON_DATE").resample("D").size().to_frame(name="count")
daily_counts["rolling_7d"] = daily_counts["count"].rolling(window=7, min_periods=1).mean()

st.line_chart(daily_counts)

# -----------------------------------------------------------
# 2) Crimes by district
# -----------------------------------------------------------
st.subheader("🏙️ Crimes by District")

dist_counts = filtered.groupby("DISTRICT").size().sort_values(ascending=False)
st.bar_chart(dist_counts)

# -----------------------------------------------------------
# 3) Top 10 offense categories pie-style
# -----------------------------------------------------------
st.subheader("🔟 Top 10 Offense Groups")

offense_counts = filtered.groupby("OFFENSE_CODE_GROUP").size().to_frame(name="count").sort_values("count", ascending=False).head(10)
st.bar_chart(offense_counts["count"])

# -----------------------------------------------------------
# 4) Incident map (sample for performance)
# -----------------------------------------------------------
st.subheader("🗺 Location of Crime Incidents (sample)")

geo = filtered.dropna(subset=["Lat", "Long"])
if len(geo) > 4000:
    geo = geo.sample(4000, random_state=42)

st.map(geo.rename(columns={"Lat": "lat", "Long": "lon"}))
