-- MediBook Row Level Security Policies
-- Run this in the Supabase SQL Editor AFTER 001_initial_schema.sql.
-- Wait 2 full minutes before running the next script.

-- Enable RLS on all patient-facing tables
ALTER TABLE clinics ENABLE ROW LEVEL SECURITY;
ALTER TABLE services ENABLE ROW LEVEL SECURITY;
ALTER TABLE slots ENABLE ROW LEVEL SECURITY;
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE reminders ENABLE ROW LEVEL SECURITY;
ALTER TABLE practitioners ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_logs ENABLE ROW LEVEL SECURITY;

-- Backend uses service_role which bypasses RLS
-- These policies protect against direct anon client access
CREATE POLICY "service_role_only" ON clinics
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_role_only" ON services
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_role_only" ON slots
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_role_only" ON patients
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_role_only" ON appointments
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_role_only" ON payments
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_role_only" ON conversation_sessions
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_role_only" ON reminders
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_role_only" ON practitioners
  FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "service_role_only" ON conversation_logs
  FOR ALL USING (auth.role() = 'service_role');
