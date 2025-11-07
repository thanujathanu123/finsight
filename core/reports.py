"""Simple report generation helper (PDF stub).

Uses ReportLab if available. For the skeleton we provide a very small
function that writes a one-page PDF with a title and simple metrics.
"""
import io
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    HAS_REPORTLAB = True
except Exception:
    HAS_REPORTLAB = False


def generate_simple_report(title: str, metrics: dict) -> bytes:
    buf = io.BytesIO()
    if not HAS_REPORTLAB:
        # Return a minimal text-based PDF-like bytes if reportlab not installed
        buf.write(f"{title}\n\n".encode('utf-8'))
        for k, v in metrics.items():
            buf.write(f"{k}: {v}\n".encode('utf-8'))
        return buf.getvalue()

    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    c.setFont('Helvetica-Bold', 16)
    c.drawString(72, height - 72, title)
    c.setFont('Helvetica', 12)
    y = height - 100
    for k, v in metrics.items():
        c.drawString(72, y, f"{k}: {v}")
        y -= 18
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()
