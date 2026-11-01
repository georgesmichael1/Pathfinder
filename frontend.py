# frontend.py
import pandas as pd
import streamlit as st
from schema import RouteOptimizationInput, StopItem
from engine import run_doa_route_engine
from chart_factory import generate_doa_convergence_chart, generate_static_route_map
from pdf_printer import create_route_pdf_report

st.set_page_config(page_title="Streamline | DOA Smart Route Optimizer", layout="wide")

st.title("🧭 Streamline | Dingo Optimization (DOA) Multi-Stop Route Planner")
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

with st.sidebar:
    st.header("1. Route & DOA Parameters")
    preset_choice = st.selectbox("Load Stop Template", list(PRESETS.keys()))
    round_trip = st.checkbox("Return to Starting Depot / Hotel (Round Trip)", value=True)
    opt_target = st.selectbox("Optimization Objective", ["Minimum Driving Time (Minutes)", "Minimum Road Distance (km)"])
    agents = st.slider("Number of Dingoes (SearchAgents_no)", 20, 150, 60, 10)
    iterations = st.slider("Max DOA Iterations (Max_iter)", 30, 300, 120, 10)
    fuel_burn = st.number_input("Vehicle Fuel Burn (L / 100km)", value=9.5, step=0.5)
    fuel_price = st.number_input("Fuel Price per Liter", value=15.0, step=0.5)
    currency = st.text_input("Currency", value="EGP")

st.subheader("📍 Editable Delivery / Tourist Stops Table (Row 1 = Fixed Starting Depot/Hotel)")
df_stops = st.data_editor(
    pd.DataFrame(PRESETS[preset_choice]),
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
        search_agents_no=agents,
        max_iterations=iterations,
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