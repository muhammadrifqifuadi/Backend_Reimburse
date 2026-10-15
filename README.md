# Reimburse API

REST API aplikasi reimburse kantor: **FastAPI + SQLAlchemy 2 + PostgreSQL**, dengan struktur
`route → controller → schema → model`, dipisah per domain.

Alur: **karyawan → HRD (menyetujui) → finance (verifikasi) → finance (membayar)**.

## Role

Hanya ada 4 role: **admin, karyawan, hrd, finance**.

| Role | Hak |
|---|---|
| `karyawan` | membuat, mengedit (saat draft/revisi), dan mengajukan klaim sendiri |
| `hrd` | **penyetuju klaim**: setujui (boleh sebagian), tolak, atau minta revisi. Juga kelola kebijakan limit, lihat semua klaim dan laporan. Boleh mengajukan klaim sendiri |
| `finance` | memverifikasi kwitansi & nominal setelah HRD, lalu membayar. Satu-satunya yang bisa melihat nomor rekening penuh dan ekspor Excel dengan nomor rekening. Boleh mengajukan klaim sendiri |
| `admin` | kelola master data dan user. **Tidak** mengajukan maupun menyetujui klaim |

Siapa pun yang ber-role `hrd` bisa menyetujui klaim (tidak per orang atau per departemen). Klaim milik HRD sendiri
diputuskan HRD lain, dan klaim milik finance dibayar finance lain, jadi **siapkan minimal 2 user HRD dan 2 user finance**.
Jika finance hanya perlu membayar tanpa tahap verifikasi, ubah `APPROVAL_STEPS` di `app/core/constants.py` menjadi `(Role.HRD,)`.

## Menjalankan

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # isi DATABASE_URL, SECRET_KEY, ENCRYPTION_KEY, dan SMTP_* (lihat "Akun & password")
uvicorn app.main:app --reload   # tabel dibuat otomatis saat pertama jalan
python -m app.seed --email admin@perusahaan.com --name "Nama Admin"   # buat ADMIN PERTAMA (password ditanya)
```

**Database milik Anda sendiri**: isi `DATABASE_URL` dengan PostgreSQL Anda
(`postgresql+psycopg2://user:password@host:5432/namadb`; database-nya dibuat dulu: `CREATE DATABASE namadb;`).
Untuk PostgreSQL lokal lewat Docker, `docker compose up -d` memakai `docker-compose.yml` di folder ini.

**Tidak ada data dummy.** Database dimulai kosong; satu-satunya data yang dibuat aplikasi adalah admin pertama di atas.
Dokumentasi: <http://localhost:8000/docs> (Swagger) dan <http://localhost:8000/rapidoc>.
Untuk RapiDoc offline, simpan `rapidoc-min.js` ke `app/static/rapidoc/`.

## Pertama kali pakai: isi data Anda sendiri

Login di Swagger lewat tombol **Authorize** (username = email), lalu isi berurutan sebagai admin:

| # | Isi | Endpoint | Wajib? |
|---|---|---|---|
| 1 | Departemen | `POST /masterdata/departments` `{"code":"OPS","name":"Operasional"}` | opsional |
| 2 | Level jabatan | `POST /masterdata/job-levels` `{"code":"STAFF","name":"Staf","rank_order":1}` | opsional, dibutuhkan untuk limit |
| 3 | Kategori klaim | `POST /masterdata/categories` `{"code":"TRANSPORT","name":"Transportasi","requires_receipt":false}` | **wajib** (tanpa kategori tidak ada yang bisa diklaim) |
| 4 | Kebijakan limit | `POST /masterdata/policies` `{"job_level_id":1,"category_id":1,"max_per_transaction":300000,"max_per_month":3000000,"require_receipt_above":50000}` | opsional |
| 5 | User | `POST /masterdata/users` `{"employee_id":"K-001","full_name":"...","email":"...","role":"hrd","department_id":1,"job_level_id":1}` (tanpa password, lihat bawah) | **wajib** (minimal 2 `hrd`, 2 `finance`, dan karyawan) |

Setelah itu setiap karyawan menambah rekening sendiri (`POST /bank-accounts`) lalu mulai mengajukan klaim.

Catatan:
- **Kode kategori menentukan isian khusus.** Kategori berkode `TRANSPORT`, `MEAL`, `LODGING`, dan `HEALTH`
  otomatis memakai isian khusus (asal/tujuan, jumlah peserta, check-in/out, data pasien). Kode lain tetap bisa dipakai,
  tanpa isian khusus. Nama kategori bebas.
- **Tanpa kebijakan limit** untuk suatu level/kategori, klaimnya tidak dibatasi (hanya aturan kwitansi umum
  `RECEIPT_REQUIRED_ABOVE` yang berlaku). Karyawan tanpa level jabatan juga tidak terkena limit.

## Tes

```bash
pytest -q                                   # SQLite sementara
TEST_DATABASE_URL=postgresql+psycopg2://... pytest -q   # PostgreSQL (gunakan database KHUSUS tes, bukan database Anda)
```
Tes memakai data dummy (`tests/demo_data.py`) hanya pada database sementara miliknya sendiri. Aplikasi tidak pernah
memuat data itu, dan database Anda tidak tersentuh.
`tests/test_flow.py` mencakup login/role guard, password sementara, ganti/lupa/reset password, rekening, validasi item, alur penuh sampai dibayar,
revisi, penolakan, pembatalan, snapshot rekening, PDF, dan Excel.

## Akun & password

Admin **tidak pernah mengisi atau mengetahui password siapa pun.**

1. **User baru**: admin hanya mengisi data (email, nama, role, dst). Sistem membuat **password sementara acak**
   (12 karakter) dan mengirimkannya ke **email karyawan** itu sendiri. Password tidak ada di respons API.
2. **Login pertama wajib ganti password.** Selama masih memakai password sementara, semua endpoint ditolak
   (`403`, `code: PASSWORD_CHANGE_REQUIRED`) kecuali `GET /auth/me` dan `POST /auth/change-password`.
   Frontend cukup membaca `user.must_change_password` dari respons login. `change-password` mengembalikan token baru.
3. **Lupa password**: `POST /auth/forgot-password {"email": "..."}` mengirim token sekali pakai (berlaku
   `RESET_TOKEN_EXPIRE_MINUTES`, default 30 menit) ke email. Lalu `POST /auth/reset-password {"token": "...", "new_password": "..."}`.
   Respons selalu sama baik email terdaftar maupun tidak, dan dibatasi 3 permintaan per jam per akun.
4. **Admin mereset akun** (mis. karyawan tidak bisa mengakses emailnya):
   `POST /masterdata/users/{id}/reset-password` mengirim password sementara baru ke email karyawan.
5. Setiap ganti/reset password atau penonaktifan akun **memutus semua sesi lama** (token lama langsung ditolak).

Aturan password: 8-72 karakter, mengandung huruf dan angka.

### Mengatur email pengirim

Kantor **tidak perlu punya server email**, dan karyawan boleh memakai **email pribadi masing-masing** (Gmail, Yahoo, dll.)
sebagai login dan penerima. Yang dibutuhkan hanya **satu akun pengirim** untuk aplikasi (mis. satu Gmail khusus, misalnya
`reimburse.perusahaan@gmail.com`; jangan pakai Gmail pribadi seseorang).

Contoh dengan Gmail:
1. Di akun Gmail pengirim, aktifkan **Verifikasi 2 Langkah** (Google Account → Keamanan).
2. Buka <https://myaccount.google.com/apppasswords>, buat App Password, salin kode 16 karakternya.
3. Isi `.env`:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=reimburse.perusahaan@gmail.com
   SMTP_PASSWORD=abcdefghijklmnop        # App Password, bukan password Gmail
   SMTP_FROM=reimburse.perusahaan@gmail.com
   ```
4. Uji sebelum membuat user: `python -m app.test_email alamat.tujuan@gmail.com`.

Catatan:
- Gmail gratis membatasi pengiriman sekitar **500 penerima per hari**, jauh di atas kebutuhan password sementara dan reset.
  Port 587 (STARTTLS) dan 465 (SSL) sama-sama didukung. Penyedia lain (Brevo, Resend, Mailgun, dll.) memakai cara yang sama:
  isi host, port, username, dan password SMTP dari dashboard mereka.
- Email dari akun Gmail biasa kadang masuk folder **Spam** penerima; minta karyawan memeriksanya.
- **Pastikan alamat email karyawan benar saat admin membuat user.** Password sementara dikirim ke alamat itu; jika salah
  ketik, orang lain yang menerimanya. Jika terjadi, gunakan `POST /masterdata/users/{id}/reset-password` atau nonaktifkan akunnya.
- Jika email gagal terkirim, pembuatan/reset user **dibatalkan** (tidak ada akun yang password-nya tak diketahui siapa pun).
- Tanpa `SMTP_HOST` dan `DEBUG=false`, membuat/mereset user ditolak (`503`). Isi email berisi password/token
  tidak pernah ditulis ke log di production.
- `DEBUG=true` (khusus development lokal): tanpa SMTP, isi email ditulis ke log server supaya Anda bisa mengambil password sementara.
- Admin pertama dibuat lewat `python -m app.seed` dengan password pilihan sendiri (tidak perlu diganti paksa).

## Struktur

```
app/
├── main.py              entry point, router, exception handler
├── seed.py              membuat admin pertama (tanpa data dummy)
├── api/routes/<domain>/ auth, masterdata, bank_account, reimbursement, approval, payment, report
├── controllers/<domain>/  logika bisnis
├── schemas/<domain>/      Pydantic request & response
├── models/<domain>/       satu file per tabel; models/registry.py mengimpor semuanya
├── core/                  config, database, security (JWT/hash), dependencies (role guard), startup, constants
├── middleware/            AuthAndLoggingMiddleware: cek Bearer token + catat request_logs
├── services/              policy_validator, approval_workflow, file_storage, pdf_generator, export_excel, email_utils, audit
├── utils/                 crypto_types (enkripsi rekening), bank_list, validators, pagination
└── static/rapidoc/
uploads/                   lampiran kwitansi (diabaikan git)
```

## Alur status

```
draft → submitted → approved_hrd → approved_finance → paid
           │             │               │
           └─────────────┴───────────────┴→ rejected (final)
                         └→ revision_requested → (edit) → submit ulang
draft / submitted / revision_requested → cancelled
```

Urutan tahap diatur di `app/core/constants.py` (`APPROVAL_STEPS`).

## Endpoint utama

| Domain | Endpoint |
|---|---|
| auth | `POST /auth/login`, `/auth/refresh`, `/auth/change-password`, `/auth/forgot-password`, `/auth/reset-password`, `GET /auth/me` |
| masterdata | `GET /masterdata/banks` (dropdown), `departments`, `job-levels`, `categories`, `policies`, `users`, `users/{id}/reset-password` |
| bank_account | `GET/POST /bank-accounts`, `PUT/DELETE /bank-accounts/{id}`, `PATCH /bank-accounts/{id}/default` |
| reimbursement | `POST/GET /reimbursements`, `GET/PUT /reimbursements/{id}`, `POST/PUT/DELETE .../items`, `POST .../items/{item_id}/attachments`, `POST .../submit`, `POST .../cancel`, `GET /reimbursements/all` |
| approval | `GET /approvals/pending`, `/approvals/history`, `POST /approvals/{id}/approve`, `/reject`, `/request-revision` |
| payment | `GET /payments/pending`, `GET /payments/{id}/destination`, `POST /payments/{id}/pay`, `GET /payments` |
| report | `GET /reports/summary`, `/reports/export` (Excel), `/reports/{id}/pdf` |

## Aturan bisnis

- **Rekening**: bank dari dropdown (atau `OTHER` + nama manual), nomor rekening & nama pemilik diketik sendiri
  (8–20 digit). Disimpan **terenkripsi** (Fernet), di API selalu masked (`******7890`).
  Saat submit, rekening di-**snapshot** ke klaim. Perubahan rekening masuk `audit_logs`.
- **Nomor rekening penuh** hanya bisa dilihat finance lewat `GET /payments/{id}/destination`
  (hanya saat klaim siap dibayar, setiap akses dicatat di audit log).
- **Tidak boleh menyetujui atau membayar klaim sendiri**, termasuk untuk HRD dan finance.
- **Persetujuan sebagian**: setiap tahap boleh menurunkan nominal disetujui per item (0 = item ditolak),
  tidak boleh menaikkan.
- **Aturan keras** (ditolak saat submit): tanggal masa depan / lebih dari `CLAIM_MAX_AGE_DAYS`, nominal di atas batas
  tanpa kwitansi, kwitansi belum diunggah, tanpa rekening, uang muka > total.
- **Aturan lunak** (ditandai `policy_flags` untuk HRD): melebihi limit per transaksi/hari/bulan/tahun menurut
  level jabatan × kategori; tanggal di luar periode klaim.
- **Kwitansi**: JPG/PNG/PDF, maks `MAX_UPLOAD_MB`, isi file dicek (magic bytes), checksum SHA-256 mencegah
  kwitansi yang sama dipakai di klaim aktif lain.
- **Data khusus kategori** (`extra_data` JSONB) divalidasi: transport (asal, tujuan, jarak, kendaraan),
  makan (jumlah & nama peserta), akomodasi (check-in/out, malam), kesehatan (pasien, hubungan, catatan).

## Memperbarui database yang sudah ada

`create_all` hanya membuat tabel baru (`password_reset_tokens` otomatis dibuat saat aplikasi start), tidak mengubah tabel
lama. Jika database Anda dibuat dari versi sebelum fitur password ini, jalankan sekali:

```sql
ALTER TABLE users ADD COLUMN must_change_password boolean NOT NULL DEFAULT false;
ALTER TABLE users ADD COLUMN token_version integer NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN password_changed_at timestamp;
```
Atau, bila belum ada data penting, kosongkan database dan jalankan ulang `python -m app.seed`.

## Catatan produksi

- Ganti `SECRET_KEY` dan isi `ENCRYPTION_KEY`. **Jangan** mengganti `ENCRYPTION_KEY` setelah ada data,
  nomor rekening lama tidak akan bisa didekripsi.
- Tabel dibuat otomatis (`AUTO_CREATE_TABLES`). Untuk production gunakan Alembic dan matikan opsi itu.
- Setelah admin pertama dibuat, hapus `ADMIN_PASSWORD` dari `.env` bila sempat diisi.
- Tambahkan rate limiting pada `/auth/login` dan `/auth/reset-password` di reverse proxy (nginx/Traefik) atau library seperti slowapi.
- Email (SMTP) wajib diisi, lihat bagian "Akun & password".

## Belum ada (sengaja ditunda)

Tabel `roles` terpisah (role disimpan sebagai kolom `users.role`), tabel `approval_flows` (urutan tahap ada di
konstanta), delegasi HRD saat cuti, persetujuan berjenjang berdasarkan nominal, notifikasi in-app, upload bukti transfer.
