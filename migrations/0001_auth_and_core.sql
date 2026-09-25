PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  email TEXT,
  full_name TEXT NOT NULL,
  school_id TEXT,
  role_code TEXT NOT NULL DEFAULT 'USER',
  status TEXT NOT NULL DEFAULT 'active',
  password_hash TEXT,
  last_login_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token_hash TEXT NOT NULL UNIQUE,
  user_id INTEGER NOT NULL,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);

CREATE TABLE IF NOT EXISTS students (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_code TEXT NOT NULL UNIQUE,
  full_name TEXT NOT NULL,
  school_name TEXT,
  cohort TEXT,
  class_name TEXT,
  cdr_status TEXT DEFAULT 'Chưa đạt',
  latest_result TEXT,
  attempts INTEGER DEFAULT 0,
  risk_level TEXT DEFAULT 'Thấp',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_students_school ON students(school_name);
CREATE INDEX IF NOT EXISTS idx_students_status ON students(cdr_status);
CREATE INDEX IF NOT EXISTS idx_students_risk ON students(risk_level);

CREATE TABLE IF NOT EXISTS care_cases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_code TEXT,
  full_name TEXT,
  school_name TEXT,
  cohort TEXT,
  risk_level TEXT DEFAULT 'Thấp',
  reason TEXT,
  status TEXT DEFAULT 'Cần theo dõi',
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_care_risk ON care_cases(risk_level);
CREATE INDEX IF NOT EXISTS idx_care_school ON care_cases(school_name);
