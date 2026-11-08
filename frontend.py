# frontend.py
import folium
from streamlit_folium
import st_folium
import re
import time
import requests
import pandas as pd
import streamlit as st
from schema import RouteOptimizationInput, StopItem
from engine import run_doa_route_engine
from chart_factory import generate_doa_convergence_chart, generate_static_route_map
from pdf_printer import create_route_pdf_report

st.set_page_config(page_title="Pathfinder | DOA Smart Route Optimizer", layout="wide")

st.title("🧭 Pathfinder | Dingo Optimization (DOA) Multi-Stop Route Planner")
st.caption("Bio-Inspired Metaheuristic Route Sequencing for Last-Mile Delivery Fleets & Multi-Stop Tourist Itineraries")

PRESETS = {
    "Cairo Last-Mile Courier (10 Delivery Drops)": [
        {"name": "Main Warehouse Depot (New Cairo)", "lat": 30.0074, "lon": 31.4913},
        {"name": "Order #101 - Nasr City Abbas El-Akkad", "lat": 30.0661, "lon": 31.3364},
        {"name": "Order #102 - Maadi Degla Square", "lat": 29.9602, "lon": 31.2769},
        {"name": "Order #103 - Heliopolis Korba", "lat": 30.0909, "lon": 31.3231},
        {"name": "Order #104 - Zamalek 26th July St", "lat": 30.0609, "lon": 31.2197},
        {"name": "Order #105 - Dokki Mossadak St", "lat": 30.0385, "lon": 31.2122},
        {"name": "Order #106 - Downtown Talaat Harb", "lat": 30.0476, "lon": 31.2384},
        {"name": "Order #107 - Mokattam Street 9", "lat": 30.0144, "lon": 31.2859},
        {"name": "Order #108 - Rehab City Gate 6", "lat": 30.0632, "lon": 31.4946},
        {"name": "Order #109 - Madinaty South Park", "lat": 30.0886, "lon": 31.6384},
    ],
    "Alexandria Tourist & Heritage Day Tour (8 Stops)": [
        {"name": "Start: Collège Saint-Marc (Shatby)", "lat": 31.2119, "lon": 29.9189},
        {"name": "Citadel of Qaitbay (Bahary)", "lat": 31.2140, "lon": 29.8856},
        {"name": "Catacombs of Kom el Shoqafa", "lat": 31.1786, "lon": 29.8929},
        {"name": "Pompey's Pillar", "lat": 31.1825, "lon": 29.8964},
        {"name": "Bibliotheca Alexandrina", "lat": 31.2089, "lon": 29.9092},
        {"name": "Roman Amphitheatre (Kom El-Dikka)", "lat": 31.1956, "lon": 29.9044},
        {"name": "Stanley Bridge", "lat": 31.2348, "lon": 29.9489},
        {"name": "Montaza Palace Gardens", "lat": 31.2885, "lon": 30.0159},
    ]
}

def resolve_line_to_coord(line: str, default_region: str = "Egypt"):
    """
    Converts a place name, Google Maps link, or raw 'Name, Lat, Lon' string
    into {'name': str, 'lat': float, 'lon': float}.
    """
    raw = line.strip()
    if not raw:
        return None

    # 1. Check for Google Maps URL or raw coordinates in the line (e.g. @30.0444,31.2357 or 30.0444, 31.2357)
    coord_match = re.search(r"(-?\d{1,2}\.\d{3,})\s*,\s*(-?\d{1,3}\.\d{3,})", raw)
    if coord_match:
        lat_val = float(coord_match.group(1))
        lon_val = float(coord_match.group(2))
        clean_name = raw.split("http")[0].strip(" ,|-:") or f"Pin ({lat_val:.4f}, {lon_val:.4f})"
        return {"name": clean_name, "lat": lat_val, "lon": lon_val}

    # 2. Otherwise geocode the place name via Free OpenStreetMap Nominatim API
    query = raw if default_region.lower() in raw.lower() else f"{raw}, {default_region}"
    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "Pathfinder-DOA-RouteEngine/1.0"}
    try:
        r = requests.get(url, params={"q": query, "format": "json", "limit": 1}, headers=headers, timeout=8)
        data = r.json()
        if data:
            return {
                "name": raw,
                "lat": round(float(data[0]["lat"]), 6),
                "lon": round(float(data[0]["lon"]), 6)
            }
    except Exception:
        pass
    return None

with st.sidebar:
    st.header("1. Route & DOA Parameters")
    preset_choice = st.selectbox("Load Preset Template", list(PRESETS.keys()))
    if st.button("🔄 Reset Table to Selected Preset"):
        st.session_state["stops_df"] = pd.DataFrame(PRESETS[preset_choice])

    round_trip = st.checkbox("Return to Starting Depot / Hotel (Round Trip)", value=True)
    opt_target = st.selectbox("Optimization Objective", ["Minimum Driving Time (Minutes)", "Minimum Road Distance (km)"])
    fuel_burn = st.number_input("Vehicle Fuel Burn (L / 100km)", value=9.5, step=0.5)
    fuel_price = st.number_input("Fuel Price per Liter", value=15.0, step=0.5)
    currency = st.text_input("Currency", value="EGP")

if "stops_df" not in st.session_state:
    st.session_state["stops_df"] = pd.DataFrame(PRESETS[preset_choice])

# ==================== SMART INPUT HUB ====================
st.subheader("⚡ Smart Stop Input")
tab_map, tab_search, tab_links, tab_csv = st.tabs([
    "🗺️ 1. Click on Map", 
    "🔍 2. Type Place Names",
    "🔗 3. Paste Links",
    "📂 4. Upload CSV"
])

with tab_map:
    st.markdown("**Click anywhere on the map to drop a pin.** It will automatically be added to your route table below.")
    
    # Center map on Cairo or Alexandria based on the first stop in the table
    start_lat = st.session_state["stops_df"].iloc[0]["lat"] if not st.session_state["stops_df"].empty else 30.0444
    start_lon = st.session_state["stops_df"].iloc[0]["lon"] if not st.session_state["stops_df"].empty else 31.2357
    
    m = folium.Map(location=[start_lat, start_lon], zoom_start=12)
    
    # Draw existing pins on the map
    for idx, row in st.session_state["stops_df"].iterrows():
        folium.Marker(
            [row["lat"], row["lon"]], 
            popup=f"{idx}: {row['name']}",
            icon=folium.Icon(color="red" if idx == 0 else "blue")
        ).add_to(m)
        
    # Render the interactive map
    map_data = st_folium(m, height=400, width=700, key="route_map")
    
    # If the user clicks the map, grab the coordinates and add it to the table
    if map_data and map_data.get("last_clicked"):
        lat = round(map_data["last_clicked"]["lat"], 6)
        lon = round(map_data["last_clicked"]["lng"], 6)
        
        # Check if we already added this exact pin to prevent duplicate re-runs
        existing = st.session_state["stops_df"]
        if not ((existing["lat"] == lat) & (existing["lon"] == lon)).any():
            new_pin = pd.DataFrame([{"name": f"Dropped Pin ({lat}, {lon})", "lat": lat, "lon": lon}])
            st.session_state["stops_df"] = pd.concat([existing, new_pin], ignore_index=True)
            st.rerun() # Instantly refreshes the UI with the new stop

with tab_search:
    col_a, col_b = st.columns([3, 1])
    with col_b:
        region_hint = st.text_input("Default Country / City Filter", value="Cairo, Egypt")
        replace_mode = st.checkbox("Replace existing table", value=True)
    with col_a:
        places_text = st.text_area(
            "Enter one location or landmark per line (Row 1 = Starting Depot/Hotel):",
            placeholder="Cairo Festival City Mall\nArkan Plaza Sheikh Zayed\nCity Stars Nasr City\nCairo Tower Zamalek\nMaadi Grand Mall",
            height=130
        )
    if st.button("🌍 Convert Place Names to Coordinates"):
        lines = [line.strip() for line in places_text.splitlines() if line.strip()]
        resolved, failed = [], []
        progress = st.progress(0, text="Geocoding stops via OpenStreetMap...")
        for idx, line in enumerate(lines):
            item = resolve_line_to_coord(line, default_region=region_hint)
            if item:
                resolved.append(item)
            else:
                failed.append(line)
            progress.progress((idx + 1) / max(1, len(lines)))
            time.sleep(1.0)  # Respect free Nominatim 1-req/sec policy
        progress.empty()

        if resolved:
            new_df = pd.DataFrame(resolved)
            st.session_state["stops_df"] = new_df if replace_mode else pd.concat([st.session_state["stops_df"], new_df], ignore_index=True)
            st.success(f"✅ Auto-located {len(resolved)} stops!")
        if failed:
            st.warning(f"⚠️ Could not find: {', '.join(failed)}. Try adding a district or city name.")

with tab_links:
    links_text = st.text_area(
        "Paste Google Maps URLs or 'Stop Name | URL' (one per line):",
        placeholder="Warehouse | https://www.google.com/maps/@30.0074,31.4913,15z\nClient A | https://www.google.com/maps?q=30.0661,31.3364",
        height=110
    )
    if st.button("📌 Extract Coordinates from Links"):
        extracted = [resolve_line_to_coord(l, "") for l in links_text.splitlines() if l.strip()]
        extracted = [x for x in extracted if x is not None]
        if extracted:
            st.session_state["stops_df"] = pd.DataFrame(extracted)
            st.success(f"✅ Extracted {len(extracted)} pins from links!")
        else:
            st.error("No coordinates found in those links. Make sure the link contains @lat,lon or ?q=lat,lon.")

with tab_csv:
    uploaded = st.file_uploader("Upload CSV with columns: name, lat, lon (or just 'name' to auto-geocode)", type=["csv"])
    if uploaded is not None:
        raw_csv = pd.read_csv(uploaded)
        if {"name", "lat", "lon"}.issubset(set(raw_csv.columns)):
            st.session_state["stops_df"] = raw_csv[["name", "lat", "lon"]].dropna()
            st.success(f"✅ Loaded {len(st.session_state['stops_df'])} stops from CSV!")

# ==================== VERIFIED COORDINATE TABLE ====================
st.subheader("📍 Verified Route Coordinate Table (Row 1 = Starting Depot/Hotel)")
df_stops = st.data_editor(
    st.session_state["stops_df"],
    num_rows="dynamic",
    use_container_width=True
)

if st.button("🐺 Run Dingo Optimization Algorithm (DOA) Route Solver", type="primary"):
    stop_items = [
        StopItem(name=str(r["name"]), lat=float(r["lat"]), lon=float(r["lon"]))
        for _, r in df_stops.dropna().iterrows()
    ]
    payload = RouteOptimizationInput(
        stops=stop_items,
        round_trip=round_trip,
        optimize_target=opt_target,
        fuel_consumption_l_per_100km=fuel_burn,
        fuel_price_per_liter=fuel_price,
        currency_label=currency
    )
    st.session_state["doa_res"] = run_doa_route_engine(payload)

if "doa_res" in st.session_state:
    res = st.session_state["doa_res"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Optimized Distance", f"{res['opt_dist_km']} km", f"-{res['dist_saved_km']} km ({res['pct_improvement']}% saved)")
    c2.metric("Optimized Drive Time", f"{res['opt_dur_min']} min", f"-{res['time_saved_min']} min saved")
    c3.metric("Estimated Fuel Cost", f"{res['opt_fuel_cost']} {res['currency']}", f"-{res['fuel_saved_cost']} {res['currency']} saved")
    c4.metric("Road Matrix Engine", res["routing_source"])

    st.markdown(f"### 👉 [Launch Optimized Multi-Stop Route in Google Maps]({res['google_maps_url']})")

    col_left, col_right = st.columns([1.2, 1])
    with col_left:
        st.subheader("Turn-by-Turn Optimized Stop Sequence")
        st.dataframe(pd.DataFrame(res["manifest"]), use_container_width=True)
    with col_right:
        conv_img = generate_doa_convergence_chart(res)
        map_img = generate_static_route_map(res)
        st.image(map_img, use_container_width=True)
        st.image(conv_img, use_container_width=True)

    st.divider()
    st.subheader("🔒 Download Official Driver Manifest PDF")
    client_key = st.text_input("Enter Client ID or Single-Report Ticket Code")
    if st.button("Verify License & Generate PDF"):
        clients = st.secrets.get("clients", {})
        tickets = st.secrets.get("single_tickets", {})
        k = client_key.strip()
        status = clients.get(k, tickets.get(k, -1))
        if status == 1:
            pdf_file = create_route_pdf_report(res, conv_img, map_img, client_id=k)
            with open(pdf_file, "rb") as f:
                st.download_button("📥 Download DOA Route Manifest PDF", data=f, file_name=pdf_file, mime="application/pdf")
        elif status == 0:
            st.error("⛔ Access Deactivated (Status = 0).")
        else:
            st.error("⛔ Invalid License Code.")
