PRAGMA foreign_keys = ON;
-- Reference (lookup) tables
CREATE TABLE IF NOT EXISTS departments(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS categories(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
-- Users (admins and students share one table, split by role)
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('admin','student')),
  department_id INTEGER REFERENCES departments(id),
  roll_no TEXT,
  year INTEGER CHECK(year BETWEEN 1 AND 4),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  category_id INTEGER REFERENCES categories(id),
  venue TEXT NOT NULL,
  start_time TEXT NOT NULL,
  capacity INTEGER NOT NULL DEFAULT 100 CHECK(capacity > 0),
  banner TEXT,
  qr_token TEXT NOT NULL UNIQUE,
  created_by INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
-- Student <-> Event (many-to-many)
CREATE TABLE IF NOT EXISTS registrations(
  id INTEGER PRIMARY KEY,
  event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  registered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(event_id, user_id));
-- Attendance can only exist for an existing registration
CREATE TABLE IF NOT EXISTS attendance(
  id INTEGER PRIMARY KEY,
  registration_id INTEGER NOT NULL UNIQUE REFERENCES registrations(id) ON DELETE CASCADE,
  marked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
-- Certificate is created pending, becomes valid only after admin approval
CREATE TABLE IF NOT EXISTS certificates(
  id INTEGER PRIMARY KEY,
  attendance_id INTEGER NOT NULL UNIQUE REFERENCES attendance(id) ON DELETE CASCADE,
  verify_code TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved')),
  approved_by INTEGER REFERENCES users(id),
  approved_at TEXT);
CREATE INDEX IF NOT EXISTS idx_reg_event ON registrations(event_id);
CREATE INDEX IF NOT EXISTS idx_reg_user ON registrations(user_id);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(start_time);
INSERT OR IGNORE INTO departments(name) VALUES
 ('Computer Engineering'),('Information Technology'),('Electronics & Telecommunication'),
 ('Electronics & Computer Science'),('Artificial Intelligence & Data Science'),
 ('Mechanical Engineering'),('Instrumentation Engineering'),('Administration');
INSERT OR IGNORE INTO categories(name) VALUES
 ('Technical'),('Cultural'),('Sports'),('Workshop'),('Seminar'),('Hackathon');
