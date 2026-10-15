"""Daftar bank untuk dropdown. Pilih 'OTHER' jika bank tidak ada di daftar."""

OTHER_CODE = "OTHER"

BANKS = [
    {"code": "BCA", "name": "Bank Central Asia (BCA)"},
    {"code": "MANDIRI", "name": "Bank Mandiri"},
    {"code": "BNI", "name": "Bank Negara Indonesia (BNI)"},
    {"code": "BRI", "name": "Bank Rakyat Indonesia (BRI)"},
    {"code": "BSI", "name": "Bank Syariah Indonesia (BSI)"},
    {"code": "CIMB", "name": "CIMB Niaga"},
    {"code": "PERMATA", "name": "Bank Permata"},
    {"code": "DANAMON", "name": "Bank Danamon"},
    {"code": "BTN", "name": "Bank Tabungan Negara (BTN)"},
    {"code": "OCBC", "name": "OCBC NISP"},
    {"code": "MAYBANK", "name": "Maybank Indonesia"},
    {"code": "PANIN", "name": "Bank Panin"},
    {"code": "MEGA", "name": "Bank Mega"},
    {"code": "BTPN", "name": "BTPN / Jenius"},
    {"code": "JAGO", "name": "Bank Jago"},
    {"code": "SEABANK", "name": "SeaBank"},
    {"code": "NEO", "name": "Bank Neo Commerce"},
    {"code": "BJB", "name": "Bank BJB"},
    {"code": "DKI", "name": "Bank DKI"},
    {"code": "JATIM", "name": "Bank Jatim"},
    {"code": "MUAMALAT", "name": "Bank Muamalat"},
]

BANK_MAP = {b["code"]: b["name"] for b in BANKS}


def all_banks() -> list[dict]:
    return BANKS + [{"code": OTHER_CODE, "name": "Lainnya (isi manual)"}]
