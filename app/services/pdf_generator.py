from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.reimbursement.reimbursement import Reimbursement
from app.utils.validators import rupiah

STATUS_LABEL = {
    "draft": "Draft", "submitted": "Menunggu HRD",
    "approved_hrd": "Disetujui HRD", "approved_finance": "Disetujui finance (menunggu bayar)",
    "paid": "Sudah dibayar", "rejected": "Ditolak", "revision_requested": "Perlu revisi", "cancelled": "Dibatalkan",
}


def build_claim_pdf(claim: Reimbursement) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=8, leading=10)
    story = [Paragraph("BUKTI REIMBURSEMENT", styles["Title"]), Spacer(1, 6)]

    info = [
        ["No. Klaim", claim.claim_number, "Status", STATUS_LABEL.get(claim.status, claim.status)],
        ["Pemohon", f"{claim.user.full_name} ({claim.user.employee_id})", "Departemen", claim.department.name if claim.department else "-"],
        ["Judul", Paragraph(claim.title, small), "Periode", f"{claim.claim_period_start:%d/%m/%Y} - {claim.claim_period_end:%d/%m/%Y}"],
        ["Tujuan", Paragraph(claim.purpose, small), "Cost center", claim.cost_center or "-"],
        ["Rekening", f"{claim.bank_name or '-'} {claim.account_number_masked or ''}", "A.n.", claim.account_holder_name or "-"],
    ]
    t = Table(info, colWidths=[2.3 * cm, 7 * cm, 2.5 * cm, 5.7 * cm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story += [t, Spacer(1, 10), Paragraph("Rincian Pengeluaran", styles["Heading3"])]

    rows = [["No", "Tanggal", "Kategori", "Keterangan", "Diajukan", "Disetujui"]]
    for i, it in enumerate(claim.items, 1):
        rows.append([
            str(i), f"{it.expense_date:%d/%m/%Y}", it.category.name,
            Paragraph(f"{it.description}" + (f" - {it.merchant_name}" if it.merchant_name else ""), small),
            rupiah(it.amount_idr),
            rupiah(it.amount_approved) if it.amount_approved is not None else "-",
        ])
    rows += [
        ["", "", "", "Total diajukan", rupiah(claim.total_claimed), ""],
        ["", "", "", "Total disetujui", "", rupiah(claim.total_approved)],
        ["", "", "", "Uang muka dipotong", "", rupiah(claim.advance_deducted)],
        ["", "", "", "TOTAL DIBAYARKAN", "", rupiah(claim.total_payable)],
    ]
    t = Table(rows, colWidths=[0.8 * cm, 2 * cm, 2.6 * cm, 6.4 * cm, 2.9 * cm, 2.9 * cm], repeatRows=1)
    n = len(claim.items)
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("GRID", (0, 0), (-1, n), 0.4, colors.grey),
        ("ALIGN", (4, 0), (5, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (3, n + 1), (-1, -1), "Helvetica-Bold"),
    ]))
    story += [t, Spacer(1, 10), Paragraph("Riwayat Persetujuan", styles["Heading3"])]

    hist = [["Waktu", "Oleh", "Peran", "Keputusan", "Catatan"]]
    for h in claim.history:
        hist.append([f"{h.created_at:%d/%m/%Y %H:%M}", h.actor_name or "-", h.actor_role, h.decision, Paragraph(h.note or "-", small)])
    t = Table(hist, colWidths=[3 * cm, 3.6 * cm, 2 * cm, 3 * cm, 6 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)
    if claim.payment:
        p = claim.payment
        story += [Spacer(1, 8), Paragraph(
            f"Dibayar pada {p.payment_date:%d/%m/%Y} sebesar {rupiah(p.amount)}, ref. {p.bank_reference or '-'}.", styles["BodyText"])]
    doc.build(story)
    return buf.getvalue()
