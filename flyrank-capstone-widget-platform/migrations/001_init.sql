-- Schema as a migration. Applied once, tracked in schema_migrations.
CREATE TABLE tenants (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  api_key_hash TEXT NOT NULL UNIQUE,      -- only a hash is stored, never the key itself
  created_at REAL NOT NULL
);

CREATE TABLE widgets (
  id TEXT PRIMARY KEY,                    -- public id used in the embed snippet
  tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  type TEXT NOT NULL CHECK (type IN ('signup_form', 'contact_form', 'cta_popover')),
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  fields_json TEXT NOT NULL,
  button_text TEXT NOT NULL,
  success_message TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,     -- bumped on every update (cache busting for config)
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE INDEX idx_widgets_tenant ON widgets(tenant_id);

CREATE TABLE submissions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  widget_id TEXT NOT NULL REFERENCES widgets(id) ON DELETE CASCADE,
  tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  data_json TEXT NOT NULL,
  ip TEXT,
  geo_country TEXT,
  geo_city TEXT,
  geo_provider TEXT,
  idempotency_key TEXT,
  created_at REAL NOT NULL
);
-- A retried submission with the same key is stored once.
CREATE UNIQUE INDEX idx_submissions_idem ON submissions(widget_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX idx_submissions_tenant_time ON submissions(tenant_id, created_at);
CREATE INDEX idx_submissions_widget_time ON submissions(widget_id, created_at);

CREATE TABLE jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'done', 'failed')),
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  run_at REAL NOT NULL,
  created_at REAL NOT NULL
);
CREATE INDEX idx_jobs_due ON jobs(status, run_at);
