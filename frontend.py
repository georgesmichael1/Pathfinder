# frontend.py
import re
import time
import folium
from streamlit_folium import st_folium
import requests
import pandas as pd
import streamlit as st
from schema import RouteOptimizationInput, StopItem
from engine import run_doa_route_engine
from chart_factory import generate_doa_convergence_chart, generate_static_route_map
from pdf_printer import create_route_pdf_report

st.set_page_config(page_title="Pathfinder | DOA Smart Route Optimizer", layout="wide")

st.title("🧭 Pathfinder | Multi-Stop Route Planner")
st.caption("Bio-Inspired Metaheuristic Route Sequencing (500 Dingoes × 200 Iterations)")


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


def update_stops_state(new_df: pd.DataFrame):
    """Safely updates stops_df and resets the data_editor widget key to prevent stale state."""
    if new_df.empty:
        clean_df = pd.DataFrame({"name": pd.Series(dtype="str"), "lat": pd.Series(dtype="float"), "lon": pd.Series(dtype="float")})
    else:
        clean_df = new_df[["name", "lat", "lon"]].dropna(subset=["lat", "lon"]).reset_index(drop=True)
    st.session_state["stops_df"] = clean_df
    st.session_state["editor_version"] = st.session_state.get("editor_version", 0) + 1


# Initialize Session State with an EMPTY table
if "stops_df" not in st.session_state:
    st.session_state["stops_df"] = pd.DataFrame({
        "name": pd.Series(dtype="str"),
        "lat": pd.Series(dtype="float"),
        "lon": pd.Series(dtype="float")
    })
if "editor_version" not in st.session_state:
    st.session_state["editor_version"] = 0
if "last_map_click" not in st.session_state:
    st.session_state["last_map_click"] = None

with st.sidebar:
    st.header("1. Route & Vehicle Settings")
    round_trip = st.checkbox("Return to Starting Depot / Hotel (Round Trip)", value=True)
    opt_target = st.selectbox("Optimization Objective", ["Minimum Driving Time (Minutes)", "Minimum Road Distance (km)"])
    fuel_burn = st.number_input("Vehicle Fuel Burn (L / 100km)", value=9.5, step=0.5)
    fuel_price = st.number_input("Fuel Price per Liter", value=15.0, step=0.5)
    currency = st.text_input("Currency", value="EGP")
    st.caption("🐺 Solver Fixed: 500 Dingoes | 200 Iterations")

# ==================== VERIFIED COORDINATE TABLE (SYNCED FIRST) ====================
st.subheader("📍 Verified Route Coordinate Table (Row 1 = Starting Depot/Hotel)")
editor_key = f"stops_editor_{st.session_state['editor_version']}"
edited_df = st.data_editor(
    st.session_state["stops_df"],
    num_rows="dynamic",
    use_container_width=True,
    key=editor_key
)

# Immediately persist any manual row deletions or edits before the map renders
if not edited_df.equals(st.session_state["stops_df"]):
    st.session_state["stops_df"] = edited_df.dropna(subset=["lat", "lon"]).reset_index(drop=True)

# ==================== SMART INPUT HUB ====================
st.subheader("⚡ Smart Stop Input")
tab_map, tab_search, tab_links, tab_csv = st.tabs([
    "🗺️ 1. Click on Map",
    "🔍 2. Type Place Names",
    "🔗 3. Paste Links",
    "📂 4. Upload CSV"
])

with tab_map:
    col_info, col_undo, col_clear = st.columns([2.5, 1, 1])
    with col_info:
        st.markdown("**Click anywhere on the map to drop a pin.** Pin 1 = Starting Depot (Red).")
    with col_undo:
        if st.button("↩️ Undo Last Pin", use_container_width=True):
            if not st.session_state["stops_df"].empty:
                update_stops_state(st.session_state["stops_df"].iloc[:-1])
                st.session_state["last_map_click"] = None
                st.rerun()
    with col_clear:
        if st.button("🗑️ Clear All Stops", use_container_width=True):
            update_stops_state(pd.DataFrame())
            st.session_state["last_map_click"] = None
            st.rerun()

    current_df = st.session_state["stops_df"].dropna(subset=["lat", "lon"]).reset_index(drop=True)

    # Center map on the most recently added pin (or default to Cairo view)
    if not current_df.empty:
        center_lat = float(current_df.iloc[-1]["lat"])
        center_lon = float(current_df.iloc[-1]["lon"])
    else:
        center_lat, center_lon = 30.0444, 31.2357

    m = folium.Map(location=[center_lat, center_lon], zoom_start=12)

    for idx, row in current_df.iterrows():
        folium.Marker(
            [float(row["lat"]), float(row["lon"])],
            popup=f"{idx + 1}. {row['name']}",
            icon=folium.Icon(color="red" if idx == 0 else "blue")
        ).add_to(m)

    map_data = st_folium(m, height=420, use_container_width=True, key="route_map")

    if map_data and map_data.get("last_clicked"):
        lat = round(float(map_data["last_clicked"]["lat"]), 6)
        lon = round(float(map_data["last_clicked"]["lng"]), 6)
        click_sig = f"{lat},{lon}"

        if st.session_state.get("last_map_click") != click_sig:
            st.session_state["last_map_click"] = click_sig
            stop_num = len(current_df) + 1
            pin_name = "Start Depot (Pin 1)" if stop_num == 1 else f"Stop #{stop_num} ({lat}, {lon})"
            new_pin = pd.DataFrame([{"name": pin_name, "lat": lat, "lon": lon}])
            updated = pd.concat([current_df, new_pin], ignore_index=True)
            update_stops_state(updated)
            st.rerun()

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
            time.sleep(1.0)
        progress.empty()

        if resolved:
            new_df = pd.DataFrame(resolved)
            combined = new_df if replace_mode else pd.concat([st.session_state["stops_df"], new_df], ignore_index=True)
            update_stops_state(combined)
            st.success(f"✅ Auto-located {len(resolved)} stops!")
            st.rerun()
        if failed:
            st.warning(f"⚠️ Could not find: {', '.join(failed)}. Try adding a district or city name.")

with tab_links:
    col_l1, col_l2 = st.columns([3, 1])
    with col_l2:
        replace_links_mode = st.checkbox("Replace existing table", value=False, key="replace_links_chk")
    with col_l1:
        links_text = st.text_area(
            "Paste one or more Google Maps URLs or 'Stop Name | URL' (adds to your existing list):",
            placeholder="Warehouse | https://www.google.com/maps/@30.0074,31.4913,15z",
            height=110
        )
    if st.button("📌 Extract & Add Coordinates from Links"):
        extracted = [resolve_line_to_coord(l, "") for l in links_text.splitlines() if l.strip()]
        extracted = [x for x in extracted if x is not None]
        if extracted:
            new_links_df = pd.DataFrame(extracted)
            # Automatically number any generic pin names based on the current table length
            current_len = 0 if replace_links_mode else len(st.session_state["stops_df"])
            for i in range(len(new_links_df)):
                if new_links_df.loc[i, "name"].startswith("Pin ("):
                    stop_num = current_len + i + 1
                    label = "Start Depot (Pin 1)" if stop_num == 1 else f"Stop #{stop_num} ({new_links_df.loc[i, 'lat']}, {new_links_df.loc[i, 'lon']})"
                    new_links_df.loc[i, "name"] = label

            combined_df = (
                new_links_df
                if replace_links_mode
                else pd.concat([st.session_state["stops_df"], new_links_df], ignore_index=True)
            )
            update_stops_state(combined_df)
            st.success(f"✅ Added {len(extracted)} stop(s) to your route table!")
            st.rerun()
        else:
            st.error("No coordinates found in that link. Make sure the link contains @lat,lon or ?q=lat,lon.")
with tab_csv:
    uploaded = st.file_uploader("Upload CSV with columns: name, lat, lon", type=["csv"])
    if uploaded is not None:
        raw_csv = pd.read_csv(uploaded)
        if {"name", "lat", "lon"}.issubset(set(raw_csv.columns)):
            update_stops_state(raw_csv[["name", "lat", "lon"]].dropna())
            st.success(f"✅ Loaded {len(st.session_state['stops_df'])} stops from CSV!")
            st.rerun()

# ==================== RUN DOA SOLVER (FIXED 500 DINGOES / 200 ITERATIONS) ====================
df_stops = st.session_state["stops_df"].dropna(subset=["lat", "lon"]).reset_index(drop=True)

if st.button("🐺 Run Dingo Optimization Algorithm (DOA) Route Solver", type="primary", use_container_width=True):
    if len(df_stops) < 2:
        st.error("Please add at least 2 stops (1 Starting Depot + 1 Destination) before running the optimizer.")
    else:
        stop_items = [
            StopItem(name=str(r["name"]), lat=float(r["lat"]), lon=float(r["lon"]))
            for _, r in df_stops.iterrows()
        ]
        payload = RouteOptimizationInput(
            stops=stop_items,
            round_trip=round_trip,
            optimize_target=opt_target,
            search_agents_no=500,
            max_iterations=200,
            fuel_consumption_l_per_100km=fuel_burn,
            fuel_price_per_liter=fuel_price,
            currency_label=currency
        )
        with st.spinner("Running 500 Dingoes × 200 Iterations across real road networks..."):
            st.session_state["doa_res"] = run_doa_route_engine(payload)

if "doa_res" in st.session_state:
    res = st.session_state["doa_res"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Optimized Distance", f"{res['opt_dist_km']} km", f"-{res['dist_saved_km']} km ({res['pct_improvement']}% saved)")
    c2.metric("Optimized Drive Time", f"{res['opt_dur_min']} min", f"-{res['time_saved_min']} min saved")
    c3.metric("Estimated Fuel Cost", f"{res['opt_fuel_cost']} {res['currency']}", f"-{res['fuel_saved_cost']} {res['currency']} saved")
    c4.metric("Road Matrix Engine", res["routing_source"])

    if "google_maps_legs" in res and len(res["google_maps_legs"]) > 1:
        st.subheader("📲 Launch Turn-by-Turn Navigation in Google Maps (Multi-Leg Relay)")
        leg_cols = st.columns(len(res["google_maps_legs"]))
        for idx, leg in enumerate(res["google_maps_legs"]):
            leg_cols[idx].markdown(f"👉 **[{leg['label']}]({leg['url']})**")
    else:
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
