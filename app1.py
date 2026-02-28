import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
import math

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(
    page_title="Food Bank Connector",
    layout="wide",
    page_icon="🍽️"
)

# -----------------------------
# LOAD DATA
# -----------------------------
@st.cache_data
def load_data():
    df = pd.read_csv("foodbanks.csv")
    return df

df = load_data()

# -----------------------------
# DATA CLEANING
# -----------------------------
df = df[[
    "organisation_name",
    "address",
    "postcode",
    "lat_lng",
    "network",
    "district"
]]

df[['latitude', 'longitude']] = df['lat_lng'].str.split(",", expand=True)
df['latitude'] = df['latitude'].astype(float)
df['longitude'] = df['longitude'].astype(float)

df = df.dropna(subset=["latitude", "longitude"])
df['city'] = df['district']
df = df.dropna(subset=["city"])

# -----------------------------
# SESSION STATE
# -----------------------------
if "registrations" not in st.session_state:
    st.session_state.registrations = 0

if "checkins" not in st.session_state:
    st.session_state.checkins = 0

if "slots" not in st.session_state:
    st.session_state.slots = {name: 50 for name in df['organisation_name']}

if "registered_bank" not in st.session_state:
    st.session_state.registered_bank = None

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "checked_in_bank" not in st.session_state:
    st.session_state.checked_in_bank = None    

# -----------------------------
# LOGIN SECTION
# -----------------------------
st.title("🍽️ Food Bank Connector")

if not st.session_state.logged_in:
    st.markdown("### Please Login to Continue")
    if st.button("Login"):
        st.session_state.logged_in = True
        st.rerun()
    st.stop()

st.markdown("### Connect with local food support services easily")

# -----------------------------
# GET USER LOCATION
# -----------------------------
location = get_geolocation()

if location:
    user_lat = location["coords"]["latitude"]
    user_lon = location["coords"]["longitude"]
else:
    user_lat = df["latitude"].mean()
    user_lon = df["longitude"].mean()

# -----------------------------
# DISTANCE CALCULATION
# -----------------------------
def calculate_distance(lat1, lon1, lat2, lon2):
    return math.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)

df["distance"] = df.apply(
    lambda row: calculate_distance(user_lat, user_lon, row["latitude"], row["longitude"]),
    axis=1
)

nearby_df = df.sort_values("distance").head(10)

# -----------------------------
# CITY FILTER (Override Option)
# -----------------------------
cities = sorted(df['city'].unique())
selected_city = st.selectbox("Search Another District", ["Nearby First"] + cities)

if selected_city != "Nearby First":
    display_df = df[df['city'] == selected_city]
else:
    display_df = nearby_df

# -----------------------------
# MAP (TOP)
# -----------------------------
st.markdown("## 🗺️ Map View")

m = folium.Map(location=[user_lat, user_lon], zoom_start=12)

# User blue marker
folium.Marker(
    [user_lat, user_lon],
    popup="You are here",
    icon=folium.Icon(color="blue")
).add_to(m)

# Food bank markers
for _, row in display_df.iterrows():
    popup_text = f"""
    <b>{row['organisation_name']}</b><br>
    {row['address']}<br>
    Postcode: {row['postcode']}<br>
    Slots: {st.session_state.slots[row['organisation_name']]}
    """
    folium.Marker(
        [row['latitude'], row['longitude']],
        popup=popup_text,
        icon=folium.Icon(color="red")
    ).add_to(m)

st_folium(m, width=1200, height=500)

# -----------------------------
# CHARTS (BELOW MAP)
# -----------------------------
st.markdown("## 📊 Live Dashboard")

col1, col2, col3 = st.columns(3)

col1.metric("Total Registrations", st.session_state.registrations)
col2.metric("Total Check-ins", st.session_state.checkins)
col3.metric("Total Available Slots", sum(st.session_state.slots.values()))

chart_df = pd.DataFrame({
    "Food Bank": list(st.session_state.slots.keys())[:10],
    "Available Slots": list(st.session_state.slots.values())[:10]
})

fig = px.bar(chart_df, x="Food Bank", y="Available Slots")
st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# CARD DISPLAY
# -----------------------------
st.markdown("## 🏦 Food Bank Listings")

for index, row in display_df.iterrows():

    st.markdown(
        f"""
        <div style="
            background-color:#111827;
            padding:20px;
            border-radius:15px;
            margin-bottom:15px;
            border:1px solid #333;
        ">
            <h3>{row['organisation_name']}</h3>
            <p>📍 {row['address']}</p>
            <p>📮 {row['postcode']}</p>
            <p>🏢 {row['network']}</p>
            <p>📊 Available Slots: {st.session_state.slots[row['organisation_name']]}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    colA, colB, colC = st.columns(3)

# ---------------- REGISTER ----------------
    with colA:
        if st.button("Register", key=f"reg_{index}"):

        # If already fully completed registration + check-in
            if st.session_state.checked_in_bank is not None:
                st.warning("You have already completed check-in. Cannot register elsewhere.")
        
        # If already registered somewhere else
            elif st.session_state.registered_bank is not None:
                st.warning(
                    f"You are already registered at {st.session_state.registered_bank}. "
                    "Please deregister first."
                )

            else:
                if st.session_state.slots[row['organisation_name']] > 0:
                    st.session_state.registered_bank = row['organisation_name']
                    st.session_state.registrations += 1
                    st.session_state.slots[row['organisation_name']] -= 1
                    st.success("Registered Successfully!")
                else:
                    st.error("No Slots Available")


# ---------------- CHECK-IN ----------------
    with colB:
        if st.button("Check-in", key=f"check_{index}"):

        # Must be registered at THIS bank
            if st.session_state.registered_bank != row['organisation_name']:
                st.warning("You must register at this location first.")
        
        # Already checked in
            elif st.session_state.checked_in_bank is not None:
                st.info("You have already checked in.")
        
            else:
                st.session_state.checked_in_bank = row['organisation_name']
                st.session_state.checkins += 1
                st.success("Check-in Successful!")


# ---------------- DEREGISTER ----------------
    with colC:
        if st.button("Deregister", key=f"dereg_{index}"):

        # Only allow deregister if registered here AND not checked in yet
            if st.session_state.registered_bank == row['organisation_name']:

                if st.session_state.checked_in_bank is not None:
                    st.warning("Cannot deregister after check-in.")
                else:
                    st.session_state.slots[row['organisation_name']] += 1
                    st.session_state.registered_bank = None
                    st.success("Deregistered Successfully!")

            else:
                st.warning("You are not registered at this location.")