from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.core.database import Base
import app.models.registry  # pastikan semua model ter-import

OUTPUT = "app/db/schema.sql"

HEADER = """-- Skema PostgreSQL Aplikasi Reimbursement
-- Dihasilkan dari model SQLAlchemy di app/models (sumber kebenarannya tetap model).
-- Aplikasi tetap membuat tabel otomatis lewat create_all saat start; file ini untuk
-- membuat database manual (psql/DBeaver) atau sebagai dokumentasi skema.
-- Data awal diisi oleh: python -m app.seed

-- Pakai:  psql -U postgres -c "CREATE DATABASE reimburse;"
--         psql -U postgres -d reimburse -f db/schema.sql
"""

dialect = postgresql.dialect()
blocks = [HEADER]

for table in Base.metadata.sorted_tables:  # urut sesuai foreign key
    lines = [str(CreateTable(table, if_not_exists=True).compile(dialect=dialect)).strip() + ";"]
    for index in sorted(table.indexes, key=lambda i: i.name):
        lines.append(str(CreateIndex(index, if_not_exists=True).compile(dialect=dialect)).strip() + ";")
    blocks.append("\n".join(lines) + "\n")

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write("\n".join(blocks))

print(f"{OUTPUT} berhasil dibuat ({len(Base.metadata.sorted_tables)} tabel)")