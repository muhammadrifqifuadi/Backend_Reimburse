from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.models.reimbursement.reimbursement import Reimbursement


def _style_header(ws, widths: list[int]) -> None:
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F4E78")
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"


def build_export(claims: list[Reimbursement], reveal_account: bool) -> bytes:
    """Rekap untuk finance. Nomor rekening penuh hanya jika reveal_account=True."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Rekap Klaim"
    ws.append([
        "No. Klaim", "NIK", "Pemohon", "Departemen", "Judul", "Periode Mulai", "Periode Selesai", "Status",
        "Total Diajukan", "Total Disetujui", "Uang Muka", "Total Dibayar", "Bank", "No. Rekening", "Atas Nama",
        "Flag Kebijakan", "Tgl Submit", "Tgl Bayar", "Ref. Transfer",
    ])
    for c in claims:
        acct = c.account_number if reveal_account else c.account_number_masked
        ws.append([
            c.claim_number, c.user.employee_id, c.user.full_name, c.department.name if c.department else "",
            c.title, c.claim_period_start, c.claim_period_end, c.status,
            float(c.total_claimed), float(c.total_approved), float(c.advance_deducted), float(c.total_payable),
            c.bank_name, acct, c.account_holder_name,
            "Ya" if c.has_policy_flag else "", c.submitted_at,
            c.payment.payment_date if c.payment else None, c.payment.bank_reference if c.payment else None,
        ])
    _style_header(ws, [22, 12, 22, 16, 30, 13, 13, 18, 16, 16, 14, 16, 18, 20, 22, 12, 18, 12, 20])
    for row in ws.iter_rows(min_row=2, min_col=9, max_col=12):
        for cell in row:
            cell.number_format = "#,##0"

    wi = wb.create_sheet("Rincian Item")
    wi.append([
        "No. Klaim", "Pemohon", "Tanggal", "Kategori", "Subkategori", "Keterangan", "Merchant", "No. Kwitansi",
        "Qty", "Harga Satuan", "Pajak", "Mata Uang", "Kurs", "Nominal IDR", "Disetujui", "Status Item",
        "Catatan Item", "Flag Kebijakan",
    ])
    for c in claims:
        for it in c.items:
            wi.append([
                c.claim_number, c.user.full_name, it.expense_date, it.category.name, it.subcategory, it.description,
                it.merchant_name, it.receipt_number, float(it.quantity), float(it.unit_price), float(it.tax_amount),
                it.currency, float(it.exchange_rate), float(it.amount_idr),
                float(it.amount_approved) if it.amount_approved is not None else None, it.item_status, it.item_note,
                "; ".join(it.policy_flags or []),
            ])
    _style_header(wi, [22, 22, 12, 16, 16, 32, 22, 16, 8, 14, 12, 8, 10, 16, 16, 12, 24, 40])
    for row in wi.iter_rows(min_row=2, min_col=10, max_col=15):
        for cell in row:
            if isinstance(cell.value, float):
                cell.number_format = "#,##0.00" if cell.column in (9, 13) else "#,##0"

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
