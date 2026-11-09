-- Skema PostgreSQL Aplikasi Reimbursement
-- Dihasilkan dari model SQLAlchemy di app/models (sumber kebenarannya tetap model).
-- Aplikasi tetap membuat tabel otomatis lewat create_all saat start; file ini untuk
-- membuat database manual (psql/DBeaver) atau sebagai dokumentasi skema.
-- Data awal diisi oleh: python -m app.seed

-- Pakai:  psql -U postgres -c "CREATE DATABASE reimburse;"
--         psql -U postgres -d reimburse -f db/schema.sql

CREATE TABLE IF NOT EXISTS audit_logs (
	id SERIAL NOT NULL, 
	user_id INTEGER, 
	action VARCHAR(50) NOT NULL, 
	entity VARCHAR(50) NOT NULL, 
	entity_id INTEGER, 
	detail JSONB NOT NULL, 
	ip_address VARCHAR(64), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs (action);
CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at);
CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs (user_id);

CREATE TABLE IF NOT EXISTS departments (
	id SERIAL NOT NULL, 
	code VARCHAR(20) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_departments_code ON departments (code);

CREATE TABLE IF NOT EXISTS expense_categories (
	id SERIAL NOT NULL, 
	code VARCHAR(20) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description VARCHAR(255), 
	requires_receipt BOOLEAN NOT NULL, 
	requires_attachment BOOLEAN NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_expense_categories_code ON expense_categories (code);

CREATE TABLE IF NOT EXISTS job_levels (
	id SERIAL NOT NULL, 
	code VARCHAR(20) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	rank_order INTEGER NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (rank_order)
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_job_levels_code ON job_levels (code);

CREATE TABLE IF NOT EXISTS request_logs (
	id SERIAL NOT NULL, 
	user_id INTEGER, 
	method VARCHAR(10) NOT NULL, 
	path VARCHAR(300) NOT NULL, 
	status_code INTEGER NOT NULL, 
	ip_address VARCHAR(64), 
	user_agent VARCHAR(300), 
	duration_ms FLOAT NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS ix_request_logs_created_at ON request_logs (created_at);
CREATE INDEX IF NOT EXISTS ix_request_logs_user_id ON request_logs (user_id);

CREATE TABLE IF NOT EXISTS reimbursement_policies (
	id SERIAL NOT NULL, 
	job_level_id INTEGER NOT NULL, 
	category_id INTEGER NOT NULL, 
	max_per_transaction NUMERIC(15, 2), 
	max_per_day NUMERIC(15, 2), 
	max_per_month NUMERIC(15, 2), 
	max_per_year NUMERIC(15, 2), 
	require_receipt_above NUMERIC(15, 2), 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_policy_level_category UNIQUE (job_level_id, category_id), 
	FOREIGN KEY(job_level_id) REFERENCES job_levels (id), 
	FOREIGN KEY(category_id) REFERENCES expense_categories (id)
);
CREATE INDEX IF NOT EXISTS ix_reimbursement_policies_category_id ON reimbursement_policies (category_id);
CREATE INDEX IF NOT EXISTS ix_reimbursement_policies_job_level_id ON reimbursement_policies (job_level_id);

CREATE TABLE IF NOT EXISTS users (
	id SERIAL NOT NULL, 
	employee_id VARCHAR(30), 
	full_name VARCHAR(100) NOT NULL, 
	email VARCHAR(150) NOT NULL, 
	phone VARCHAR(30), 
	hashed_password VARCHAR(255) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	department_id INTEGER, 
	job_level_id INTEGER, 
	is_active BOOLEAN NOT NULL, 
	must_change_password BOOLEAN DEFAULT false NOT NULL, 
	token_version INTEGER DEFAULT '0' NOT NULL, 
	password_changed_at TIMESTAMP WITHOUT TIME ZONE, 
	last_login_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(department_id) REFERENCES departments (id), 
	FOREIGN KEY(job_level_id) REFERENCES job_levels (id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_employee_id ON users (employee_id);
CREATE INDEX IF NOT EXISTS ix_users_role ON users (role);

CREATE TABLE IF NOT EXISTS bank_accounts (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	bank_code VARCHAR(20) NOT NULL, 
	bank_name VARCHAR(100) NOT NULL, 
	account_number VARCHAR(512) NOT NULL, 
	account_holder_name VARCHAR(100) NOT NULL, 
	is_default BOOLEAN NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE INDEX IF NOT EXISTS ix_bank_accounts_user_id ON bank_accounts (user_id);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	used_at TIMESTAMP WITHOUT TIME ZONE, 
	ip_address VARCHAR(64), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_created_at ON password_reset_tokens (created_at);
CREATE UNIQUE INDEX IF NOT EXISTS ix_password_reset_tokens_token_hash ON password_reset_tokens (token_hash);
CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_user_id ON password_reset_tokens (user_id);

CREATE TABLE IF NOT EXISTS reimbursements (
	id SERIAL NOT NULL, 
	claim_number VARCHAR(30) NOT NULL, 
	user_id INTEGER NOT NULL, 
	department_id INTEGER, 
	job_level_id INTEGER, 
	cost_center VARCHAR(50), 
	project_code VARCHAR(50), 
	title VARCHAR(200) NOT NULL, 
	description TEXT, 
	purpose TEXT NOT NULL, 
	claim_period_start DATE NOT NULL, 
	claim_period_end DATE NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	subtotal NUMERIC(15, 2) NOT NULL, 
	tax_total NUMERIC(15, 2) NOT NULL, 
	total_claimed NUMERIC(15, 2) NOT NULL, 
	total_approved NUMERIC(15, 2) NOT NULL, 
	advance_deducted NUMERIC(15, 2) NOT NULL, 
	total_payable NUMERIC(15, 2) NOT NULL, 
	bank_code VARCHAR(20), 
	bank_name VARCHAR(100), 
	account_number VARCHAR(512), 
	account_holder_name VARCHAR(100), 
	status VARCHAR(25) NOT NULL, 
	current_step VARCHAR(20), 
	has_policy_flag BOOLEAN NOT NULL, 
	submitted_at TIMESTAMP WITHOUT TIME ZONE, 
	rejected_reason TEXT, 
	revision_note TEXT, 
	cancelled_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	created_by INTEGER, 
	updated_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(department_id) REFERENCES departments (id), 
	FOREIGN KEY(job_level_id) REFERENCES job_levels (id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_reimbursements_claim_number ON reimbursements (claim_number);
CREATE INDEX IF NOT EXISTS ix_reimbursements_current_step ON reimbursements (current_step);
CREATE INDEX IF NOT EXISTS ix_reimbursements_status ON reimbursements (status);
CREATE INDEX IF NOT EXISTS ix_reimbursements_user_id ON reimbursements (user_id);

CREATE TABLE IF NOT EXISTS approval_histories (
	id SERIAL NOT NULL, 
	reimbursement_id INTEGER NOT NULL, 
	step VARCHAR(20), 
	actor_id INTEGER NOT NULL, 
	actor_role VARCHAR(20) NOT NULL, 
	decision VARCHAR(25) NOT NULL, 
	note TEXT, 
	amount_before NUMERIC(15, 2), 
	amount_after NUMERIC(15, 2), 
	ip_address VARCHAR(64), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(reimbursement_id) REFERENCES reimbursements (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
);
CREATE INDEX IF NOT EXISTS ix_approval_histories_actor_id ON approval_histories (actor_id);
CREATE INDEX IF NOT EXISTS ix_approval_histories_reimbursement_id ON approval_histories (reimbursement_id);

CREATE TABLE IF NOT EXISTS payments (
	id SERIAL NOT NULL, 
	reimbursement_id INTEGER NOT NULL, 
	paid_by INTEGER NOT NULL, 
	payment_date DATE NOT NULL, 
	amount NUMERIC(15, 2) NOT NULL, 
	bank_name VARCHAR(100), 
	account_number_masked VARCHAR(30), 
	bank_reference VARCHAR(100), 
	note TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	proof_file_path VARCHAR(255), 
	PRIMARY KEY (id), 
	UNIQUE (reimbursement_id), 
	FOREIGN KEY(reimbursement_id) REFERENCES reimbursements (id), 
	FOREIGN KEY(paid_by) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS reimbursement_items (
	id SERIAL NOT NULL, 
	reimbursement_id INTEGER NOT NULL, 
	category_id INTEGER NOT NULL, 
	subcategory VARCHAR(100), 
	expense_date DATE NOT NULL, 
	description VARCHAR(255) NOT NULL, 
	merchant_name VARCHAR(150), 
	location VARCHAR(150), 
	receipt_number VARCHAR(80), 
	receipt_date DATE, 
	has_receipt BOOLEAN NOT NULL, 
	no_receipt_reason TEXT, 
	quantity NUMERIC(12, 2) NOT NULL, 
	unit_price NUMERIC(15, 2) NOT NULL, 
	amount NUMERIC(15, 2) NOT NULL, 
	tax_amount NUMERIC(15, 2) NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	exchange_rate NUMERIC(18, 6) NOT NULL, 
	amount_idr NUMERIC(15, 2) NOT NULL, 
	payment_method VARCHAR(20) NOT NULL, 
	extra_data JSONB NOT NULL, 
	amount_approved NUMERIC(15, 2), 
	item_status VARCHAR(15) NOT NULL, 
	item_note TEXT, 
	policy_flags JSONB NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(reimbursement_id) REFERENCES reimbursements (id), 
	FOREIGN KEY(category_id) REFERENCES expense_categories (id)
);
CREATE INDEX IF NOT EXISTS ix_reimbursement_items_category_id ON reimbursement_items (category_id);
CREATE INDEX IF NOT EXISTS ix_reimbursement_items_expense_date ON reimbursement_items (expense_date);
CREATE INDEX IF NOT EXISTS ix_reimbursement_items_reimbursement_id ON reimbursement_items (reimbursement_id);

CREATE TABLE IF NOT EXISTS attachments (
	id SERIAL NOT NULL, 
	reimbursement_id INTEGER NOT NULL, 
	item_id INTEGER NOT NULL, 
	file_name VARCHAR(255) NOT NULL, 
	file_path VARCHAR(500) NOT NULL, 
	mime_type VARCHAR(100) NOT NULL, 
	size INTEGER NOT NULL, 
	checksum VARCHAR(64) NOT NULL, 
	uploaded_by INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(reimbursement_id) REFERENCES reimbursements (id), 
	FOREIGN KEY(item_id) REFERENCES reimbursement_items (id)
);
CREATE INDEX IF NOT EXISTS ix_attachments_checksum ON attachments (checksum);
CREATE INDEX IF NOT EXISTS ix_attachments_item_id ON attachments (item_id);
CREATE INDEX IF NOT EXISTS ix_attachments_reimbursement_id ON attachments (reimbursement_id);
