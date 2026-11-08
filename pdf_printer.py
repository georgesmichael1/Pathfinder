# pdf_printer.py
from fpdf import FPDF
from typing import Dict, Any


def create_route_pdf_report(
    res: Dict[str, Any],
    conv_chart_path: str,
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
    pdf.cell(0, 6, "PATHFINDER | OFFICIAL DRIVER MANIFEST & NAVIGATION", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_x(10)
    pdf.cell(0, 5, f"Client License: {client_id}  |  Routing Engine: {res['routing_source']} (500 Dingoes x 200 Iter)", ln=True)

    # KPI Summary Strip
    pdf.ln(8)
    pdf.set_text_color(15, 23, 42)
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.cell(
        0, 6,
        f"Optimized Distance: {res['opt_dist_km']} km (Saved {res['dist_saved_km']} km / -{res['pct_improvement']}%)   |   "
        f"Drive Time: {res['opt_dur_min']} min (Saved {res['time_saved_min']} min)   |   "
        f"Fuel Cost: {res['opt_fuel_cost']} {res['currency']} (Saved {res['fuel_saved_cost']} {res['currency']})",
        ln=True
    )

    # DOA Convergence & Savings Chart (Centered, Clean Layout without ugly static map)
    pdf.ln(2)
    y_top = pdf.get_y()
    pdf.image(conv_chart_path, x=22, y=y_top, w=165)
    pdf.set_y(y_top + 64)

    # Clickable Google Maps Navigation Section (Exclusive to PDF)
    pdf.set_fill_color(240, 249, 255)
    pdf.set_draw_color(2, 132, 199)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, "1. Clickable Turn-by-Turn Google Maps Navigation Links:", ln=True, fill=True)

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(2, 132, 199)
    legs = res.get("google_maps_legs", [{"label": "Full Route Navigation", "url": res["google_maps_url"]}])
    for leg in legs:
        pdf.cell(
            0, 6,
            f">> Click to Open in Google Maps: {leg['label']}",
            ln=True,
            link=leg["url"]
        )

    # Turn-by-Turn Sequenced Stop Manifest Table (Exclusive to PDF)
    pdf.ln(3)
    pdf.set_text_color(15, 23, 42)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "2. Official Sequenced Stop Order (Driver Manifest):", ln=True)

    pdf.set_fill_color(226, 232, 240)
    pdf.set_draw_color(148, 163, 184)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(14, 6, "Order", 1, 0, "C", True)
    pdf.cell(82, 6, "Location / Stop Name", 1, 0, "L", True)
    pdf.cell(30, 6, "Leg Dist (km)", 1, 0, "C", True)
    pdf.cell(30, 6, "Leg Time (min)", 1, 0, "C", True)
    pdf.cell(34, 6, "Cumul. Time (min)", 1, 1, "C", True)

    pdf.set_font("Helvetica", "", 8)
    for row in res["manifest"]:
        safe_name = str(row["name"]).encode("latin-1", "replace").decode("latin-1")[:44]
        pdf.cell(14, 5.5, str(row["step"]), 1, 0, "C")
        pdf.cell(82, 5.5, safe_name, 1, 0, "L")
        pdf.cell(30, 5.5, f"{row['leg_dist_km']:.2f}", 1, 0, "C")
        pdf.cell(30, 5.5, f"{row['leg_time_min']:.1f}", 1, 0, "C")
        pdf.cell(34, 5.5, f"{row['cum_time_min']:.1f}", 1, 1, "C")

    pdf.output(output_filename)
    return output_filename
