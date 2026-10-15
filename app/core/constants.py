class Role:
    KARYAWAN = "karyawan"
    HRD = "hrd"
    FINANCE = "finance"
    ADMIN = "admin"
    ALL = (KARYAWAN, HRD, FINANCE, ADMIN)


class Status:
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED_HRD = "approved_hrd"
    APPROVED_FINANCE = "approved_finance"
    PAID = "paid"
    REJECTED = "rejected"
    REVISION = "revision_requested"
    CANCELLED = "cancelled"

    EDITABLE = (DRAFT, REVISION)
    CANCELABLE = (DRAFT, SUBMITTED, REVISION)
    # status yang dihitung sebagai "terpakai" untuk limit & laporan
    ACTIVE = (SUBMITTED, APPROVED_HRD, APPROVED_FINANCE, PAID)


class Decision:
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION = "revision_requested"
    CANCELLED = "cancelled"
    PAID = "paid"


# Tahap persetujuan: HRD menyetujui -> finance memverifikasi -> finance membayar.
# Nama tahap = nama role yang berhak memutuskannya. Ubah urutan/isi di sini jika kantor berbeda
# (mis. APPROVAL_STEPS = (Role.HRD,) jika finance hanya membayar tanpa tahap persetujuan).
APPROVAL_STEPS = (Role.HRD, Role.FINANCE)
STEP_PAYMENT = "payment"  # semua persetujuan selesai, menunggu finance membayar

STATUS_AFTER_STEP = {
    Role.HRD: Status.APPROVED_HRD,
    Role.FINANCE: Status.APPROVED_FINANCE,
}

PAYMENT_METHODS = ("cash", "personal_card", "ewallet", "transfer")

ITEM_PENDING = "pending"
ITEM_APPROVED = "approved"
ITEM_PARTIAL = "partial"
ITEM_REJECTED = "rejected"
