from __future__ import annotations

import datetime as dt
import json

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


# Expect a JSON file with: items: [{title, category, y_hat, q10, q90, images[], provenance_strength}]
def render_pdf(in_path: str, out_path: str):
    with open(in_path) as f:
        data = json.load(f)
    c = canvas.Canvas(out_path, pagesize=A4)
    width, height = A4
    margin = 36
    y = height - margin

    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, y, "Portfolio Insurance Report")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(margin, y, f"Generated: {dt.datetime.now(dt.timezone.utc).isoformat()}Z")
    y -= 30

    total = 0.0
    for it in data.get("items", []):
        if y < 120:
            c.showPage()
            y = height - margin
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin, y, it.get("title", "(untitled)"))
        y -= 14
        c.setFont("Helvetica", 9)
        line = f"{it.get('category','?')} | Value €{it.get('y_hat','?')} (range €{it.get('q10','?')}–€{it.get('q90','?')}) | Provenance: {it.get('provenance_strength','unknown')}"
        c.drawString(margin, y, line)
        y -= 12
        total += float(it.get("y_hat", 0) or 0)

    y -= 12
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, f"Estimated Total: €{round(total,2)}")
    c.save()


if __name__ == "__main__":
    import sys

    in_path = sys.argv[1] if len(sys.argv) > 1 else "portfolio_export.json"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "portfolio_insurance.pdf"
    render_pdf(in_path, out_path)
    print(out_path)
