-- MediBook Performance Indexes
-- Run this in the Supabase SQL Editor AFTER 002_rls_policies.sql.

CREATE INDEX IF NOT EXISTS idx_slots_clinic_date_status ON slots(clinic_id, slot_date, status);
CREATE INDEX IF NOT EXISTS idx_slots_locked_until ON slots(locked_until) WHERE status = 'locked';
CREATE INDEX IF NOT EXISTS idx_appointments_booking_ref ON appointments(booking_reference);
CREATE INDEX IF NOT EXISTS idx_payments_source_ref ON payments(source_reference);
CREATE INDEX IF NOT EXISTS idx_sessions_clinic_patient ON conversation_sessions(clinic_id, patient_whatsapp);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON conversation_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_reminders_scheduled ON reminders(scheduled_for, status);
CREATE INDEX IF NOT EXISTS idx_logs_clinic_created ON conversation_logs(clinic_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_practitioners_clinic ON practitioners(clinic_id);
