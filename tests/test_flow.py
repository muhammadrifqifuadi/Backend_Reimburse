import os
import re
from datetime import date, timedelta

import pytest

TODAY = date.today()


def png(seed: str) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + seed.encode() * 20


def mail_value(outbox, email, pattern):
    mails = [m for m in outbox if email in m["to"]]
    assert mails, f"tidak ada email ke {email}"
    return re.search(pattern, mails[-1]["body"]).group(1)


def temp_password(outbox, email):
    return mail_value(outbox, email, r"Password sementara: (\S+)")


def activate_user(client, outbox, email, new_password="PasswordBaru1"):
    """Login dengan password sementara dari email lalu ganti password; mengembalikan header Authorization."""
    r = client.post("/auth/login", data={"username": email, "password": temp_password(outbox, email)})
    assert r.status_code == 200, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.post("/auth/change-password", headers=h, json={"current_password": temp_password(outbox, email), "new_password": new_password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def new_pw_not_in(payload, outbox, email) -> bool:
    """Password sementara tidak boleh muncul di respons API (hanya di email)."""
    return temp_password(outbox, email) not in str(payload)


def cats(client, h):
    return {c["code"]: c["id"] for c in client.get("/masterdata/categories", headers=h).json()}


def new_claim(client, h, **kw):
    body = {
        "title": "Kunjungan klien Bandung", "purpose": "Meeting dengan klien proyek X",
        "claim_period_start": str(TODAY - timedelta(days=5)), "claim_period_end": str(TODAY),
        **kw,
    }
    r = client.post("/reimbursements", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def item_body(category_id, **kw):
    base = {"category_id": category_id, "expense_date": str(TODAY - timedelta(days=2)),
            "description": "Taksi online ke kantor klien", "quantity": 1, "unit_price": 150000,
            "tax_amount": 0, "payment_method": "ewallet", "merchant_name": "Grab"}
    base.update(kw)
    return base


def transport_extra():
    return {"origin": "Kantor", "destination": "Kantor klien", "distance_km": 12.5, "vehicle_type": "taxi_online"}


def upload(client, h, claim_id, item_id, seed):
    return client.post(f"/reimbursements/{claim_id}/items/{item_id}/attachments", headers=h,
                       files={"file": (f"{seed}.png", png(seed), "image/png")})


# ---------------------------------------------------------------- auth & middleware
def test_requires_token(client):
    assert client.get("/reimbursements").status_code == 401
    assert client.get("/reimbursements", headers={"Authorization": "Bearer salah"}).status_code == 401
    assert client.post("/auth/login", data={"username": "employee@kantor.test", "password": "x"}).status_code == 401


def test_role_guard(client, tokens):
    assert client.get("/approvals/pending", headers=tokens["employee"]).status_code == 403  # karyawan bukan penyetuju
    assert client.get("/approvals/pending", headers=tokens["admin"]).status_code == 403
    assert client.post("/masterdata/departments", json={"code": "ZZ", "name": "Zzz"}, headers=tokens["employee"]).status_code == 403
    assert client.get("/reports/summary", headers=tokens["employee"]).status_code == 403
    assert client.post("/reimbursements", json={}, headers=tokens["admin"]).status_code == 403  # admin tidak mengajukan klaim


def test_refresh_and_me(client):
    r = client.post("/auth/login", data={"username": "employee@kantor.test", "password": "Password123!"}).json()
    assert r["user"]["role"] == "karyawan" and r["user"]["job_level"]["code"] == "STAFF"
    r2 = client.post("/auth/refresh", json={"refresh_token": r["refresh_token"]})
    assert r2.status_code == 200
    assert client.post("/auth/refresh", json={"refresh_token": r["access_token"]}).status_code == 401  # bukan refresh token


# ---------------------------------------------------------------- bank account
def test_bank_accounts(client, tokens):
    h = tokens["employee2"]
    banks = client.get("/masterdata/banks", headers=h).json()
    assert banks[0]["code"] == "BCA" and banks[-1]["code"] == "OTHER"

    bad = client.post("/bank-accounts", headers=h, json={"bank_code": "BCA", "account_number": "12ab", "account_holder_name": "Siti"})
    assert bad.status_code == 422
    other = client.post("/bank-accounts", headers=h, json={"bank_code": "OTHER", "account_holder_name": "Siti Aminah", "account_number": "9988776655"})
    assert other.status_code == 422  # nama bank wajib

    a1 = client.post("/bank-accounts", headers=h, json={"bank_code": "mandiri", "account_number": "123-456-7890", "account_holder_name": "Siti Aminah"})
    assert a1.status_code == 201, a1.text
    assert a1.json()["account_number_masked"] == "******7890" and a1.json()["is_default"] is True  # otomatis default
    a2 = client.post("/bank-accounts", headers=h, json={"bank_code": "OTHER", "bank_name_other": "Bank Daerah X",
                                                         "account_number": "5550001112223", "account_holder_name": "Siti Aminah", "is_default": True})
    assert a2.status_code == 201 and a2.json()["bank_name"] == "Bank Daerah X"
    lst = client.get("/bank-accounts", headers=h).json()
    assert [a["is_default"] for a in lst] == [True, False] and lst[0]["id"] == a2.json()["id"]
    assert client.post("/bank-accounts", headers=h, json={"bank_code": "MANDIRI", "account_number": "1234567890", "account_holder_name": "Siti Aminah"}).status_code == 409
    assert client.delete(f"/bank-accounts/{a2.json()['id']}", headers=h).status_code == 204
    assert client.get("/bank-accounts", headers=h).json()[0]["id"] == a1.json()["id"]  # default berpindah


# ---------------------------------------------------------------- validasi item
def test_item_validation(client, tokens):
    h = tokens["employee"]
    c = cats(client, h)
    claim = new_claim(client, h)
    cid = claim["id"]
    # tanggal terlalu lama
    old = item_body(c["TRANSPORT"], expense_date=str(TODAY - timedelta(days=45)), extra_data=transport_extra())
    assert client.post(f"/reimbursements/{cid}/items", json=old, headers=h).status_code == 422
    # tanggal masa depan
    fut = item_body(c["TRANSPORT"], expense_date=str(TODAY + timedelta(days=1)), extra_data=transport_extra())
    assert client.post(f"/reimbursements/{cid}/items", json=fut, headers=h).status_code == 422
    # data khusus kategori tidak lengkap
    r = client.post(f"/reimbursements/{cid}/items", json=item_body(c["TRANSPORT"], extra_data={"origin": "A"}), headers=h)
    assert r.status_code == 422 and r.json()["detail"]["errors"]
    # tanpa kwitansi wajib alasan
    r = client.post(f"/reimbursements/{cid}/items", json=item_body(c["TRANSPORT"], has_receipt=False, extra_data=transport_extra()), headers=h)
    assert r.status_code == 422
    # akomodasi: nights harus cocok
    lod = item_body(c["LODGING"], extra_data={"check_in": str(TODAY - timedelta(days=4)), "check_out": str(TODAY - timedelta(days=2)), "nights": 5})
    assert client.post(f"/reimbursements/{cid}/items", json=lod, headers=h).status_code == 422
    # mata uang asing wajib kurs
    usd = item_body(c["OFFICE"], currency="USD")
    assert client.post(f"/reimbursements/{cid}/items", json=usd, headers=h).status_code == 422
    # orang lain tidak bisa mengubah klaim ini
    assert client.post(f"/reimbursements/{cid}/items", json=item_body(c["TRANSPORT"], extra_data=transport_extra()), headers=tokens["employee2"]).status_code == 404


def test_submit_blockers(client, tokens):
    h = tokens["employee"]
    c = cats(client, h)
    claim = new_claim(client, h)
    r = client.post(f"/reimbursements/{claim['id']}/submit", headers=h)
    assert r.status_code == 422 and "item" in str(r.json()).lower()
    claim = client.post(f"/reimbursements/{claim['id']}/items", json=item_body(c["TRANSPORT"], extra_data=transport_extra()), headers=h).json()
    r = client.post(f"/reimbursements/{claim['id']}/submit", headers=h)  # belum ada file kwitansi
    assert r.status_code == 422 and any("kwitansi" in e for e in r.json()["detail"]["errors"])
    assert upload(client, h, claim["id"], claim["items"][0]["id"], "blocker-1").status_code == 201
    # tanpa kwitansi & di atas batas: ditolak sistem
    big = client.post(f"/reimbursements/{claim['id']}/items", json=item_body(
        c["OFFICE"], description="Beli printer kecil", unit_price=800000, has_receipt=False, no_receipt_reason="Hilang"), headers=h).json()
    r = client.post(f"/reimbursements/{claim['id']}/submit", headers=h)
    assert r.status_code == 422 and any("wajib disertai kwitansi" in e for e in r.json()["detail"]["errors"])
    # file palsu (isi bukan PNG) & kwitansi ganda
    fake = client.post(f"/reimbursements/{claim['id']}/items/{claim['items'][0]['id']}/attachments", headers=h,
                       files={"file": ("x.png", b"bukan gambar", "image/png")})
    assert fake.status_code == 422
    dup = upload(client, h, claim["id"], claim["items"][0]["id"], "blocker-1")
    assert dup.status_code == 409


# ---------------------------------------------------------------- alur lengkap
def test_full_flow(client, tokens):
    emp, hrd, fin = tokens["employee"], tokens["hrd"], tokens["finance"]
    c = cats(client, emp)

    claim = new_claim(client, emp, items=[
        item_body(c["TRANSPORT"], extra_data=transport_extra()),
        item_body(c["MEAL"], description="Makan siang bersama klien", unit_price=200000, tax_amount=20000,
                  extra_data={"participants_count": 3, "attendee_names": ["Andi", "Klien A", "Klien B"], "meal_type": "lunch"}),
    ])
    assert claim["status"] == "draft" and claim["claim_number"].startswith("REM/")
    assert claim["total_claimed"] == 370000 and claim["tax_total"] == 20000
    cid = claim["id"]
    # item makan 220.000 > limit per transaksi STAFF (150.000) -> akan ditandai
    for it in claim["items"]:
        assert upload(client, emp, cid, it["id"], f"flow-{it['id']}").status_code == 201

    r = client.post(f"/reimbursements/{cid}/submit", headers=emp)
    assert r.status_code == 200, r.text
    claim = r.json()
    assert claim["status"] == "submitted" and claim["current_step"] == "hrd"
    assert claim["account_number_masked"] == "******7890" and claim["has_policy_flag"] is True
    meal = next(i for i in claim["items"] if i["category"]["code"] == "MEAL")
    assert any("limit per transaksi" in f for f in meal["policy_flags"])
    assert "account_number" not in claim  # nomor penuh tidak pernah keluar

    # tidak bisa diedit setelah submit
    assert client.post(f"/reimbursements/{cid}/items", json=item_body(c["TRANSPORT"], extra_data=transport_extra()), headers=emp).status_code == 409
    # pemohon & karyawan lain tidak bisa menyetujui; finance belum gilirannya
    assert client.post(f"/approvals/{cid}/approve", headers=emp).status_code == 403
    assert client.post(f"/approvals/{cid}/approve", headers=tokens["employee2"]).status_code == 403
    assert client.post(f"/approvals/{cid}/approve", headers=fin).status_code == 403

    # HRD (semua user ber-role hrd) melihat klaim ini di daftar pending; finance belum
    for h in (hrd, tokens["hrd2"]):
        pend = client.get("/approvals/pending", headers=h).json()
        assert cid in [x["id"] for x in pend["items"]]
    assert cid not in [x["id"] for x in client.get("/approvals/pending", headers=fin).json()["items"]]

    # HRD: setujui sebagian (item makan diturunkan jadi 150.000)
    r = client.post(f"/approvals/{cid}/approve", headers=hrd, json={
        "note": "Makan siang dibatasi limit", "items": [{"item_id": meal["id"], "amount_approved": 150000, "note": "Sesuai limit"}]})
    assert r.status_code == 200, r.text
    claim = r.json()
    assert claim["status"] == "approved_hrd" and claim["current_step"] == "finance"
    assert claim["total_approved"] == 300000
    assert next(i for i in claim["items"] if i["id"] == meal["id"])["item_status"] == "partial"
    # tidak boleh menaikkan nominal di tahap berikutnya
    r = client.post(f"/approvals/{cid}/approve", headers=fin, json={"items": [{"item_id": meal["id"], "amount_approved": 220000}]})
    assert r.status_code == 422
    # HRD tidak bisa memutuskan lagi (sudah lewat tahapnya)
    assert client.post(f"/approvals/{cid}/approve", headers=hrd).status_code == 403

    claim = client.post(f"/approvals/{cid}/approve", headers=fin, json={"note": "Kwitansi lengkap"}).json()
    assert claim["status"] == "approved_finance" and claim["current_step"] == "payment"

    # pembayaran: hanya finance, nomor rekening penuh dicatat audit
    assert client.post(f"/payments/{cid}/pay", headers=hrd, json={"payment_date": str(TODAY), "bank_reference": "TRX1"}).status_code == 403
    assert client.get("/payments/pending", headers=fin).json()["total"] >= 1
    dest = client.get(f"/payments/{cid}/destination", headers=fin).json()
    assert dest["account_number"] == "1234567890" and dest["amount_payable"] == 300000
    r = client.post(f"/payments/{cid}/pay", headers=fin, json={"payment_date": str(TODAY), "bank_reference": "TRX-2026-0001"})
    assert r.status_code == 200, r.text
    claim = r.json()
    assert claim["status"] == "paid" and claim["payment"]["amount"] == 300000
    assert [h["decision"] for h in claim["history"]] == ["submitted", "approved", "approved", "paid"]
    assert client.post(f"/payments/{cid}/pay", headers=fin, json={"payment_date": str(TODAY), "bank_reference": "TRX-2"}).status_code == 409

    # akses & laporan
    assert client.get(f"/reimbursements/{cid}", headers=tokens["employee2"]).status_code == 404
    assert client.get(f"/reimbursements/{cid}", headers=hrd).status_code == 200
    pdf = client.get(f"/reports/{cid}/pdf", headers=emp)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    xl = client.get("/reports/export", headers=fin)
    assert xl.status_code == 200 and xl.content[:2] == b"PK"
    assert client.get("/reports/export", headers=emp).status_code == 403
    s = client.get("/reports/summary", headers=hrd).json()
    assert any(x["status"] == "paid" for x in s["by_status"]) and s["by_category"]
    dl = client.get(f"/reimbursements/attachments/{claim['items'][0]['attachments'][0]['id']}/download", headers=hrd)
    assert dl.status_code == 200 and dl.content.startswith(b"\x89PNG")
    assert client.get(f"/reimbursements/attachments/{claim['items'][0]['attachments'][0]['id']}/download", headers=tokens["employee2"]).status_code == 404


def test_revision_and_reject(client, tokens):
    emp, hrd = tokens["employee"], tokens["hrd"]
    c = cats(client, emp)
    claim = new_claim(client, emp, items=[item_body(c["TRANSPORT"], extra_data=transport_extra(), description="Taksi pulang lembur")])
    cid, iid = claim["id"], claim["items"][0]["id"]
    assert upload(client, emp, cid, iid, "rev-1").status_code == 201
    assert client.post(f"/reimbursements/{cid}/submit", headers=emp).status_code == 200

    # catatan wajib
    assert client.post(f"/approvals/{cid}/request-revision", headers=hrd, json={"note": "x"}).status_code == 422
    r = client.post(f"/approvals/{cid}/request-revision", headers=hrd, json={"note": "Lampirkan bukti lembur dari HR"})
    assert r.status_code == 200 and r.json()["status"] == "revision_requested" and r.json()["current_step"] is None
    assert r.json()["revision_note"].startswith("Lampirkan")

    # pemohon revisi lalu submit ulang
    r = client.put(f"/reimbursements/{cid}/items/{iid}", headers=emp, json=item_body(
        c["TRANSPORT"], extra_data=transport_extra(), description="Taksi pulang lembur (bukti lembur terlampir)"))
    assert r.status_code == 200
    # lampiran lama tetap ada; submit ulang
    r = client.post(f"/reimbursements/{cid}/submit", headers=emp)
    assert r.status_code == 200 and r.json()["current_step"] == "hrd"

    r = client.post(f"/approvals/{cid}/reject", headers=hrd, json={"note": "Bukan keperluan dinas"})
    assert r.status_code == 200 and r.json()["status"] == "rejected" and r.json()["rejected_reason"]
    assert client.post(f"/approvals/{cid}/approve", headers=hrd).status_code == 403  # final
    assert client.put(f"/reimbursements/{cid}", headers=emp, json={"title": "Ubah judul"}).status_code == 409
    hist = client.get("/approvals/history", headers=hrd).json()
    assert cid in [x["id"] for x in hist["items"]]


def test_cancel_and_snapshot(client, tokens):
    emp = tokens["employee"]
    c = cats(client, emp)
    claim = new_claim(client, emp, items=[item_body(c["TRANSPORT"], extra_data=transport_extra(), description="Parkir klien")])
    cid, iid = claim["id"], claim["items"][0]["id"]
    assert upload(client, emp, cid, iid, "snap-1").status_code == 201
    r = client.post(f"/reimbursements/{cid}/submit", headers=emp)
    assert r.json()["bank_name"] == "Bank Central Asia (BCA)"
    # ganti rekening default setelah submit -> klaim lama tidak berubah
    new = client.post("/bank-accounts", headers=emp, json={"bank_code": "BNI", "account_number": "0099887766", "account_holder_name": "Andi Pratama", "is_default": True})
    assert new.status_code == 201
    assert client.get(f"/reimbursements/{cid}", headers=emp).json()["account_number_masked"] == "******7890"
    r = client.post(f"/reimbursements/{cid}/cancel", headers=emp, json={"reason": "Salah input"})
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert client.post(f"/reimbursements/{cid}/cancel", headers=emp).status_code == 409


def test_masterdata_admin(client, tokens, outbox):
    ad = tokens["admin"]
    r = client.post("/masterdata/users", headers=ad, json={
        "employee_id": "EMP-099", "full_name": "Karyawan Baru", "email": "baru@kantor.co.id",
        "role": "karyawan", "department_id": 1, "job_level_id": 1})
    assert r.status_code == 201, r.text
    assert "password" not in str(r.json()).lower().replace("must_change_password", "")  # admin tidak menerima password
    assert client.post("/masterdata/users", headers=ad, json={
        "employee_id": "EMP-099", "full_name": "Dup", "email": "dup@kantor.co.id"}).status_code == 409
    assert client.post("/auth/login", data={"username": "baru@kantor.co.id", "password": temp_password(outbox, "baru@kantor.co.id")}).status_code == 200
    assert client.put(f"/masterdata/users/{r.json()['id']}", headers=ad, json={"is_active": False}).status_code == 200
    assert client.post("/auth/login", data={"username": "baru@kantor.co.id", "password": temp_password(outbox, "baru@kantor.co.id")}).status_code == 401
    pol = client.get("/masterdata/policies?job_level_id=1", headers=ad).json()
    assert len(pol) == 8
    assert client.put(f"/masterdata/policies/{pol[0]['id']}", headers=tokens["hrd"], json={"max_per_transaction": 999999}).json()["max_per_transaction"] == 999999


def test_hrd_and_finance_own_claims(client, tokens):
    """Klaim milik HRD diputuskan HRD lain; klaim milik finance disetujui & dibayar finance lain."""
    hrd, hrd2, fin, fin2 = tokens["hrd"], tokens["hrd2"], tokens["finance"], tokens["finance2"]
    for h, name in ((hrd, "Rina"), (fin, "Budi")):
        assert client.post("/bank-accounts", headers=h, json={
            "bank_code": "BRI", "account_number": "7788990011", "account_holder_name": f"{name} Pemilik"}).status_code == 201

    def make_claim(h, seed):
        c = cats(client, h)
        cl = new_claim(client, h, items=[item_body(c["TRANSPORT"], extra_data=transport_extra(), description=f"Taksi {seed}")])
        assert upload(client, h, cl["id"], cl["items"][0]["id"], seed).status_code == 201
        r = client.post(f"/reimbursements/{cl['id']}/submit", headers=h)
        assert r.status_code == 200, r.text
        return r.json()

    # --- klaim HRD
    cid = make_claim(hrd, "own-hrd")["id"]
    assert client.post(f"/approvals/{cid}/approve", headers=hrd).status_code == 403  # tidak boleh menyetujui sendiri
    assert cid not in [x["id"] for x in client.get("/approvals/pending", headers=hrd).json()["items"]]
    assert cid in [x["id"] for x in client.get("/approvals/pending", headers=hrd2).json()["items"]]
    assert client.post(f"/approvals/{cid}/approve", headers=hrd2).json()["current_step"] == "finance"

    # --- klaim finance: HRD menyetujui, finance lain memverifikasi dan membayar
    cid = make_claim(fin, "own-fin")["id"]
    assert client.post(f"/approvals/{cid}/approve", headers=hrd).json()["current_step"] == "finance"
    assert client.post(f"/approvals/{cid}/approve", headers=fin).status_code == 403
    assert client.post(f"/approvals/{cid}/approve", headers=fin2).json()["current_step"] == "payment"
    pay = {"payment_date": str(TODAY), "bank_reference": "TRX-OWN-FIN"}
    assert client.post(f"/payments/{cid}/pay", headers=fin, json=pay).status_code == 403  # tidak boleh bayar klaim sendiri
    assert client.get(f"/payments/{cid}/destination", headers=fin).status_code == 403
    assert client.post(f"/payments/{cid}/pay", headers=fin2, json=pay).json()["status"] == "paid"


def test_user_without_level_or_policy(client, tokens, outbox):
    """Data milik pengguna sendiri bisa belum lengkap: tanpa departemen, level jabatan, dan kebijakan limit."""
    ad, hrd, fin = tokens["admin"], tokens["hrd"], tokens["finance"]
    r = client.post("/masterdata/users", headers=ad, json={
        "employee_id": "NEW-001", "full_name": "Pengguna Baru", "email": "baru1@kantor.co.id"})
    assert r.status_code == 201 and r.json()["department"] is None and r.json()["job_level"] is None
    h = activate_user(client, outbox, "baru1@kantor.co.id")

    assert client.post("/bank-accounts", headers=h, json={
        "bank_code": "BNI", "account_number": "5566778899", "account_holder_name": "Pengguna Baru"}).status_code == 201
    c = cats(client, h)
    claim = new_claim(client, h, items=[item_body(
        c["MEAL"], description="Makan siang tim", unit_price=90000, extra_data={"participants_count": 2})])
    cid = claim["id"]
    assert upload(client, h, cid, claim["items"][0]["id"], "nolevel-1").status_code == 201
    r = client.post(f"/reimbursements/{cid}/submit", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["has_policy_flag"] is False and r.json()["department"] is None  # tanpa kebijakan = tanpa flag limit

    assert client.post(f"/approvals/{cid}/approve", headers=hrd).status_code == 200
    assert client.post(f"/approvals/{cid}/approve", headers=fin).status_code == 200
    r = client.post(f"/payments/{cid}/pay", headers=fin, json={"payment_date": str(TODAY), "bank_reference": "TRX-NOLEVEL"})
    assert r.status_code == 200 and r.json()["status"] == "paid"
    assert client.get(f"/reports/{cid}/pdf", headers=h).content.startswith(b"%PDF")
    assert client.get("/reports/export", headers=fin).status_code == 200
    assert client.get("/reports/summary", headers=hrd).status_code == 200


def test_fresh_database_has_no_dummy_data(tmp_path):
    """`python -m app.seed` pada database kosong hanya membuat 1 admin dan tidak mengisi data lain."""
    import sqlite3
    import subprocess
    import sys

    db_file = tmp_path / "fresh.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_file}", "ADMIN_EMAIL": "pemilik@perusahaan.co.id",
           "ADMIN_NAME": "Pemilik Sistem", "ADMIN_PASSWORD": "RahasiaBanget1"}
    run = lambda: subprocess.run([sys.executable, "-m", "app.seed"], env=env, capture_output=True, text=True,
                                 cwd=os.path.dirname(os.path.dirname(__file__)))
    first = run()
    assert first.returncode == 0 and "Admin dibuat" in first.stdout, first.stderr
    assert "sudah ada" in run().stdout  # aman dijalankan ulang

    con = sqlite3.connect(db_file)
    count = lambda t: con.execute(f"select count(*) from {t}").fetchone()[0]
    assert count("users") == 1 and con.execute("select role, email from users").fetchone() == ("admin", "pemilik@perusahaan.co.id")
    for table in ("departments", "job_levels", "expense_categories", "reimbursement_policies",
                  "bank_accounts", "reimbursements", "payments"):
        assert count(table) == 0, table
    con.close()


# ---------------------------------------------------------------- akun & password
def test_temp_password_and_forced_change(client, tokens, outbox):
    ad = tokens["admin"]
    email = "wajib.ganti@kantor.co.id"
    r = client.post("/masterdata/users", headers=ad, json={"employee_id": "PW-001", "full_name": "Wajib Ganti", "email": email})
    assert r.status_code == 201 and r.json()["must_change_password"] is True
    mail = outbox[-1]
    assert mail["to"] == [email] and "WAJIB mengganti password" in mail["body"]
    temp = temp_password(outbox, email)
    assert len(temp) == 12 and re.search(r"[A-Za-z]", temp) and re.search(r"\d", temp)

    login = client.post("/auth/login", data={"username": email, "password": temp})
    assert login.status_code == 200 and login.json()["user"]["must_change_password"] is True
    h = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # sebelum ganti password: hanya /auth/me dan /auth/change-password yang boleh
    assert client.get("/auth/me", headers=h).status_code == 200
    for path in ("/reimbursements", "/bank-accounts", "/masterdata/categories"):
        r = client.get(path, headers=h)
        assert r.status_code == 403 and r.json()["detail"]["code"] == "PASSWORD_CHANGE_REQUIRED", path

    cp = lambda cur, new: client.post("/auth/change-password", headers=h, json={"current_password": cur, "new_password": new})
    assert cp("salah-salah1", "PasswordBaru1").status_code == 400  # password saat ini salah
    assert cp(temp, temp).status_code == 400  # harus berbeda
    assert cp(temp, "pendek1").status_code == 422  # < 8 karakter
    assert cp(temp, "hanyahuruf").status_code == 422  # tanpa angka
    assert cp(temp, "12345678").status_code == 422  # tanpa huruf

    r = cp(temp, "PasswordBaru1")
    assert r.status_code == 200
    new_h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/auth/me", headers=h).status_code == 401  # token lama otomatis mati
    assert client.get("/reimbursements", headers=h).status_code == 401
    assert client.get("/auth/me", headers=new_h).json()["must_change_password"] is False
    assert client.get("/bank-accounts", headers=new_h).status_code == 200  # sekarang boleh
    assert client.post("/auth/login", data={"username": email, "password": temp}).status_code == 401
    assert client.post("/auth/login", data={"username": email, "password": "PasswordBaru1"}).status_code == 200
    # refresh token lama (sebelum ganti password) ditolak
    assert client.post("/auth/refresh", json={"refresh_token": login.json()["refresh_token"]}).status_code == 401


def test_forgot_and_reset_password(client, tokens, outbox):
    ad = tokens["admin"]
    email = "lupa@kantor.co.id"
    client.post("/masterdata/users", headers=ad, json={"employee_id": "PW-002", "full_name": "Si Pelupa", "email": email})
    h = activate_user(client, outbox, email, "PasswordLama1")
    n = len(outbox)

    # email tidak terdaftar: respons sama persis, tidak ada email terkirim
    unknown = client.post("/auth/forgot-password", json={"email": "tidak.ada@kantor.co.id"})
    known = client.post("/auth/forgot-password", json={"email": email.upper()})
    assert unknown.status_code == known.status_code == 200 and unknown.json() == known.json()
    assert len(outbox) == n + 1 and outbox[-1]["to"] == [email]
    token = mail_value(outbox, email, r"Token reset: (\S+)")

    rp = lambda t, pw: client.post("/auth/reset-password", json={"token": t, "new_password": pw})
    assert rp("token-ngawur", "PasswordBaru2").status_code == 400
    assert rp(token, "pendek").status_code == 422
    r = rp(token, "PasswordBaru2")
    assert r.status_code == 200
    assert rp(token, "PasswordBaru3").status_code == 400  # sekali pakai
    assert client.get("/auth/me", headers=h).status_code == 401  # sesi lama diputus
    assert client.post("/auth/login", data={"username": email, "password": "PasswordLama1"}).status_code == 401
    assert client.post("/auth/login", data={"username": email, "password": "PasswordBaru2"}).status_code == 200

    # permintaan baru membatalkan token sebelumnya
    client.post("/auth/forgot-password", json={"email": email})
    t1 = mail_value(outbox, email, r"Token reset: (\S+)")
    client.post("/auth/forgot-password", json={"email": email})
    t2 = mail_value(outbox, email, r"Token reset: (\S+)")
    assert t1 != t2 and rp(t1, "PasswordBaru4").status_code == 400
    # maksimal 3 permintaan per jam: yang ke-4 tidak mengirim email
    client.post("/auth/forgot-password", json={"email": email})
    count = len(outbox)
    client.post("/auth/forgot-password", json={"email": email})
    assert len(outbox) == count
    assert rp(t2, "PasswordBaru5").status_code == 200  # permintaan yang diblokir tidak membatalkan token yang masih berlaku


def test_reset_token_expiry(client, tokens, outbox):
    from datetime import timedelta
    from sqlalchemy import update
    from app.core.database import SessionLocal, utcnow
    from app.models.auth.password_reset_token import PasswordResetToken

    email = "kedaluwarsa@kantor.co.id"
    client.post("/masterdata/users", headers=tokens["admin"], json={"employee_id": "PW-003", "full_name": "Kedaluwarsa", "email": email})
    client.post("/auth/forgot-password", json={"email": email})
    token = mail_value(outbox, email, r"Token reset: (\S+)")
    with SessionLocal() as db:
        db.execute(update(PasswordResetToken).values(expires_at=utcnow() - timedelta(minutes=1)))
        db.commit()
    assert client.post("/auth/reset-password", json={"token": token, "new_password": "PasswordBaru1"}).status_code == 400


def test_admin_reset_password(client, tokens, outbox):
    ad = tokens["admin"]
    email = "direset@kantor.co.id"
    uid = client.post("/masterdata/users", headers=ad, json={"employee_id": "PW-004", "full_name": "Di Reset", "email": email}).json()["id"]
    h = activate_user(client, outbox, email, "PasswordLama1")
    assert client.get("/bank-accounts", headers=h).status_code == 200

    assert client.post(f"/masterdata/users/{uid}/reset-password", headers=tokens["hrd"]).status_code == 403
    admin_id = client.get("/auth/me", headers=ad).json()["id"]
    assert client.post(f"/masterdata/users/{admin_id}/reset-password", headers=ad).status_code == 400  # akun sendiri

    r = client.post(f"/masterdata/users/{uid}/reset-password", headers=ad)
    assert r.status_code == 200 and set(r.json()) == {"message"} and new_pw_not_in(r.json(), outbox, email)
    new_temp = temp_password(outbox, email)
    assert "direset oleh admin" in outbox[-1]["body"]
    assert client.get("/bank-accounts", headers=h).status_code == 401  # sesi lama diputus
    assert client.post("/auth/login", data={"username": email, "password": "PasswordLama1"}).status_code == 401
    r = client.post("/auth/login", data={"username": email, "password": new_temp})
    assert r.status_code == 200 and r.json()["user"]["must_change_password"] is True  # kembali wajib ganti

    # akun nonaktif memutus sesi yang masih berjalan
    h2 = activate_user(client, outbox, email, "PasswordBaru9")
    assert client.put(f"/masterdata/users/{uid}", headers=ad, json={"is_active": False}).status_code == 200
    assert client.get("/auth/me", headers=h2).status_code == 401
    assert client.post(f"/masterdata/users/{uid}/reset-password", headers=ad).status_code == 409


def test_email_failure_does_not_leave_orphan_account(client, tokens, monkeypatch):
    from app.services import email_utils

    def fail(*a, **k):
        raise email_utils.EmailError("smtp down")

    monkeypatch.setattr(email_utils, "send_now", fail)
    body = {"employee_id": "PW-005", "full_name": "Gagal Kirim", "email": "gagal@kantor.co.id"}
    assert client.post("/masterdata/users", headers=tokens["admin"], json=body).status_code == 502
    monkeypatch.undo()  # email kembali normal: akun yang sama bisa dibuat (tidak ada sisa akun yatim)
    monkeypatch.setattr(email_utils, "send_now", lambda *a, **k: None)
    assert client.post("/masterdata/users", headers=tokens["admin"], json=body).status_code == 201


def test_no_smtp_in_production_refuses_to_create_user(client, tokens, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "DEBUG", False)
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    r = client.post("/masterdata/users", headers=tokens["admin"], json={"employee_id": "PW-006", "full_name": "Tanpa Smtp", "email": "tanpasmtp@kantor.co.id"})
    assert r.status_code == 503
    monkeypatch.setattr(settings, "DEBUG", True)
    assert client.post("/masterdata/users", headers=tokens["admin"], json={"employee_id": "PW-006", "full_name": "Tanpa Smtp", "email": "tanpasmtp@kantor.co.id"}).status_code == 201


def test_smtp_port_modes(monkeypatch):
    """Port 587 memakai STARTTLS, port 465 memakai SSL langsung."""
    import smtplib
    from app.core.config import settings
    from app.services import email_utils

    calls = []

    class Fake:
        def __init__(self, kind): self.kind = kind
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): calls.append((self.kind, "starttls"))
        def login(self, u, p): calls.append((self.kind, "login", u))
        def send_message(self, m): calls.append((self.kind, "send", m["To"]))

    monkeypatch.setattr(smtplib, "SMTP", lambda *a, **k: Fake("SMTP"))
    monkeypatch.setattr(smtplib, "SMTP_SSL", lambda *a, **k: Fake("SSL"))
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.contoh.com")
    monkeypatch.setattr(settings, "SMTP_USER", "kirim@contoh.com")

    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    email_utils._smtp_send(["a@b.com"], "s", "b")
    assert calls == [("SMTP", "starttls"), ("SMTP", "login", "kirim@contoh.com"), ("SMTP", "send", "a@b.com")]
    calls.clear()
    monkeypatch.setattr(settings, "SMTP_PORT", 465)
    email_utils._smtp_send(["a@b.com"], "s", "b")
    assert calls == [("SSL", "login", "kirim@contoh.com"), ("SSL", "send", "a@b.com")]  # tanpa starttls
