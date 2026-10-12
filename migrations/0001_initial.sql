PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS schools (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','INACTIVE')),
  data_status TEXT NOT NULL DEFAULT 'CHUA_CO_DU_LIEU' CHECK (data_status IN ('CHUA_CO_DU_LIEU','DA_CO_DU_LIEU')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_schools_status ON schools(status);
CREATE TABLE IF NOT EXISTS students (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_code TEXT NOT NULL UNIQUE,
  full_name TEXT,
  school_id INTEGER,
  major TEXT,
  cohort TEXT,
  class_name TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (school_id) REFERENCES schools(id) ON UPDATE CASCADE ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_students_school ON students(school_id);
CREATE INDEX IF NOT EXISTS idx_students_cohort ON students(cohort);
CREATE INDEX IF NOT EXISTS idx_students_major ON students(major);
CREATE TABLE IF NOT EXISTS care_cases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL,
  care_level TEXT NOT NULL DEFAULT 'THEO_DOI' CHECK (care_level IN ('ON_DINH','THEO_DOI','CAN_TU_VAN','NGUY_CO_CAO')),
  reason TEXT,
  status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','IN_PROGRESS','RESOLVED','CLOSED')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (student_id) REFERENCES students(id) ON UPDATE CASCADE ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_care_cases_student ON care_cases(student_id);
CREATE INDEX IF NOT EXISTS idx_care_cases_level ON care_cases(care_level);
CREATE INDEX IF NOT EXISTS idx_care_cases_status ON care_cases(status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_care_cases_student_open ON care_cases(student_id) WHERE status IN ('OPEN','IN_PROGRESS');
INSERT OR IGNORE INTO schools (code, name, status, data_status) VALUES
('SPKT','Trường Đại học Sư phạm Kỹ thuật','ACTIVE','CHUA_CO_DU_LIEU'),
('BKA','Trường Đại học Bách khoa','ACTIVE','CHUA_CO_DU_LIEU'),
('SP','Trường Đại học Sư phạm','ACTIVE','CHUA_CO_DU_LIEU'),
('DUE','Trường Đại học Kinh tế','ACTIVE','CHUA_CO_DU_LIEU'),
('VKU','Trường Đại học CNTT&TT Việt-Hàn','ACTIVE','CHUA_CO_DU_LIEU'),
('YD','Trường Đại học Y-Dược','ACTIVE','CHUA_CO_DU_LIEU');
