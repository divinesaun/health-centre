-- MediBook Initial Schema
-- Run this in the Supabase SQL Editor.
-- Wait 2 full minutes before running the next script.

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- PRACTITIONERS (referenced by slots and appointments)
CREATE TABLE IF NOT EXISTS practitioners (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id UUID NOT NULL,
  name VARCHAR(255) NOT NULL,
  specialisation VARCHAR(255),
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- CLINICS (tenants)
CREATE TABLE IF NOT EXISTS clinics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  whatsapp_number VARCHAR(20) UNIQUE NOT NULL,
  twilio_account_sid VARCHAR(100),
  twilio_auth_token VARCHAR(200),
  timezone VARCHAR(50) DEFAULT 'Africa/Harare',
  is_active BOOLEAN DEFAULT true,
  subscription_tier VARCHAR(50) DEFAULT 'basic',
  greeting_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add FK from practitioners to clinics after clinics is created
ALTER TABLE practitioners
  ADD CONSTRAINT fk_practitioners_clinic
  FOREIGN KEY (clinic_id) REFERENCES clinics(id) ON DELETE CASCADE;

-- SERVICES
CREATE TABLE IF NOT EXISTS services (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id UUID REFERENCES clinics(id) ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL,
  duration_minutes INT DEFAULT 30,
  booking_fee_usd NUMERIC(10,2) DEFAULT 0.00,
  is_active BOOLEAN DEFAULT true,
  display_order INT DEFAULT 0
);

-- SLOTS
CREATE TABLE IF NOT EXISTS slots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id UUID REFERENCES clinics(id) ON DELETE CASCADE,
  practitioner_id UUID REFERENCES practitioners(id),
  service_id UUID REFERENCES services(id),
  slot_date DATE NOT NULL,
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  status VARCHAR(20) DEFAULT 'available'
    CHECK (status IN ('available','locked','booked','cancelled')),
  locked_until TIMESTAMPTZ,
  locked_by_session VARCHAR(100)
);

-- PATIENTS
CREATE TABLE IF NOT EXISTS patients (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id UUID REFERENCES clinics(id) ON DELETE CASCADE,
  whatsapp_number VARCHAR(20) NOT NULL,
  name VARCHAR(255),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(clinic_id, whatsapp_number)
);

-- APPOINTMENTS
CREATE TABLE IF NOT EXISTS appointments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id UUID REFERENCES clinics(id) ON DELETE CASCADE,
  patient_id UUID REFERENCES patients(id),
  slot_id UUID REFERENCES slots(id),
  service_id UUID REFERENCES services(id),
  practitioner_id UUID REFERENCES practitioners(id),
  status VARCHAR(30) DEFAULT 'pending_payment'
    CHECK (status IN ('pending_payment','confirmed','completed','cancelled','no_show')),
  booking_reference VARCHAR(20) UNIQUE NOT NULL,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  confirmed_at TIMESTAMPTZ
);

-- PAYMENTS
CREATE TABLE IF NOT EXISTS payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id UUID REFERENCES clinics(id),
  appointment_id UUID REFERENCES appointments(id),
  amount_usd NUMERIC(10,2) NOT NULL,
  currency VARCHAR(10) DEFAULT 'USD',
  provider VARCHAR(50) DEFAULT 'ecocash',
  source_reference UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
  customer_msisdn VARCHAR(20),
  status VARCHAR(30) DEFAULT 'pending'
    CHECK (status IN ('pending','processing','paid','failed','refunded','expired')),
  failure_reason TEXT,
  initiated_at TIMESTAMPTZ DEFAULT NOW(),
  confirmed_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ
);

-- CONVERSATION SESSIONS
CREATE TABLE IF NOT EXISTS conversation_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id UUID REFERENCES clinics(id) ON DELETE CASCADE,
  patient_whatsapp VARCHAR(20) NOT NULL,
  state VARCHAR(100) NOT NULL DEFAULT 'IDLE',
  context JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '30 minutes'),
  UNIQUE(clinic_id, patient_whatsapp)
);

-- REMINDERS
CREATE TABLE IF NOT EXISTS reminders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  appointment_id UUID REFERENCES appointments(id),
  clinic_id UUID REFERENCES clinics(id),
  scheduled_for TIMESTAMPTZ NOT NULL,
  sent_at TIMESTAMPTZ,
  status VARCHAR(20) DEFAULT 'pending'
    CHECK (status IN ('pending','sent','failed'))
);

-- CONVERSATION LOGS (audit)
CREATE TABLE IF NOT EXISTS conversation_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id UUID REFERENCES clinics(id),
  patient_whatsapp VARCHAR(20) NOT NULL,
  direction VARCHAR(10) NOT NULL CHECK (direction IN ('inbound','outbound')),
  message_text TEXT,
  flow_state VARCHAR(100),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
