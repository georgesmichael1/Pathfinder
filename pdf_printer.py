# pdf_printer.py
from fpdf import FPDF
from typing import Dict, Any


def create_route_pdf_report(
    res: Dict[str, Any],
    conv_chart_path: str,
    map_chart_path: str,
    client_id: str,
    output_filename: str = "DOA_Route_Manifest.pdf"
) -> str:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    # Header Banner
    pdf.set_fill_color(15, 23, 42)
    pdf.rect(0, 0, 210, 24, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_xy(10, 6)
    pdf.cell(0, 6, "STREAMLINE | DINGO OPTIMIZATION ROUTE MANIFEST", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_x(10)
    pdf.cell(0, 5, f"Client License: {client_id}  |  Routing Engine: {res['routing_source']}", ln=True)

    pdf.ln(8)
    pdf.set_text_color(15, 23, 42)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(
        0, 6,
        f"Optimized Distance: {res['opt_dist_km']} km (Saved {res['dist_saved_km']} km / -{res['pct_improvement']}%)   |   "
        f"Drive Time: {res['opt_dur_min']} min (Saved {res['time_saved_min']} min)   |   "
        f"Fuel Cost: {res['opt_fuel_cost']} {res['currency']}",
        ln=True
    )

    # Charts Row
    pdf.ln(2)
    y_top = pdf.get_y()
    pdf.image(conv_chart_path, x=10, y=y_top, w=115)
    pdf.image(map_chart_path, x=128, y=y_top, w=72)
    pdf.set_y(y_top + 52)

    # Turn-by-Turn Manifest Table
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Turn-by-Turn Sequenced Stop Manifest", ln=True)
    pdf.set_fill_color(226, 232, 240)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(14, 6, "Order", 1, 0, "C", True)
    pdf.cell(78, 6, "Location / Stop Name", 1, 0, "L", True)
    pdf.cell(32, 6, "Leg Dist (km)", 1, 0, "C", True)
    pdf.cell(32, 6, "Leg Time (min)", 1, 0, "C", True)
    pdf.cell(34, 6, "Cumul. Time (min)", 1, 1, "C", True)

    pdf.set_font("Helvetica", "", 8)
    for row in res["manifest"]:
        pdf.cell(14, 5.5, str(row["step"]), 1, 0, "C")
        pdf.cell(78, 5.5, str(row["name"])[:42], 1, 0, "L")
        pdf.cell(32, 5.5, f"{row['leg_dist_km']:.2f}", 1, 0, "C")
        pdf.cell(32, 5.5, f"{row['leg_time_min']:.1f}", 1, 0, "C")
        pdf.cell(34, 5.5, f"{row['cum_time_min']:.1f}", 1, 1, "C")

    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(2, 132, 199)
    pdf.cell(0, 5, "Click Here to Launch Turn-by-Turn Route Directly in Google Maps", ln=True, link=res["google_maps_url"])

    pdf.output(output_filename)
    return output_filename