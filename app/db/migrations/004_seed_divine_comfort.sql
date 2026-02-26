-- Seed data for Divine Comfort Clinic
-- Run this in the Supabase SQL Editor AFTER the indexes script.
-- This inserts the clinic, a practitioner, sample services, and sample slots.
-- The app also auto-seeds the clinic on startup, but this script adds
-- richer seed data for testing.

-- Insert the clinic (skip if already exists via app auto-seed)
INSERT INTO clinics (name, whatsapp_number, timezone, is_active, subscription_tier, greeting_message)
VALUES (
  'Divine Comfort Clinic',
  '14155238886',
  'Africa/Harare',
  true,
  'premium',
  'Welcome to Divine Comfort Clinic!'
)
ON CONFLICT (whatsapp_number) DO UPDATE SET
  name = EXCLUDED.name,
  greeting_message = EXCLUDED.greeting_message;

-- Get the clinic ID for subsequent inserts
DO $$
DECLARE
  v_clinic_id UUID;
  v_prac_id UUID;
  v_svc_general UUID;
  v_svc_eye UUID;
  v_svc_dental UUID;
BEGIN
  SELECT id INTO v_clinic_id FROM clinics WHERE whatsapp_number = '14155238886';

  -- Insert a practitioner
  INSERT INTO practitioners (clinic_id, name, specialisation, is_active)
  VALUES (v_clinic_id, 'Dr. Moyo', 'General Practice', true)
  ON CONFLICT DO NOTHING
  RETURNING id INTO v_prac_id;

  IF v_prac_id IS NULL THEN
    SELECT id INTO v_prac_id FROM practitioners
    WHERE clinic_id = v_clinic_id AND name = 'Dr. Moyo' LIMIT 1;
  END IF;

  -- Insert services
  INSERT INTO services (clinic_id, name, duration_minutes, booking_fee_usd, is_active, display_order)
  VALUES
    (v_clinic_id, 'General Consultation', 30, 3.00, true, 1),
    (v_clinic_id, 'Eye Test', 45, 5.00, true, 2),
    (v_clinic_id, 'Dental Check-up', 60, 7.00, true, 3)
  ON CONFLICT DO NOTHING;

  SELECT id INTO v_svc_general FROM services
  WHERE clinic_id = v_clinic_id AND name = 'General Consultation' LIMIT 1;

  -- Insert sample slots for the next 5 weekdays
  FOR i IN 0..4 LOOP
    -- Skip weekends
    IF EXTRACT(DOW FROM CURRENT_DATE + i) NOT IN (0, 6) THEN
      INSERT INTO slots (clinic_id, practitioner_id, service_id, slot_date, start_time, end_time, status)
      VALUES
        (v_clinic_id, v_prac_id, NULL, CURRENT_DATE + i, '08:00', '08:30', 'available'),
        (v_clinic_id, v_prac_id, NULL, CURRENT_DATE + i, '08:30', '09:00', 'available'),
        (v_clinic_id, v_prac_id, NULL, CURRENT_DATE + i, '09:00', '09:30', 'available'),
        (v_clinic_id, v_prac_id, NULL, CURRENT_DATE + i, '09:30', '10:00', 'available'),
        (v_clinic_id, v_prac_id, NULL, CURRENT_DATE + i, '10:00', '10:30', 'available'),
        (v_clinic_id, v_prac_id, NULL, CURRENT_DATE + i, '10:30', '11:00', 'available'),
        (v_clinic_id, v_prac_id, NULL, CURRENT_DATE + i, '11:00', '11:30', 'available'),
        (v_clinic_id, v_prac_id, NULL, CURRENT_DATE + i, '14:00', '14:30', 'available'),
        (v_clinic_id, v_prac_id, NULL, CURRENT_DATE + i, '14:30', '15:00', 'available'),
        (v_clinic_id, v_prac_id, NULL, CURRENT_DATE + i, '15:00', '15:30', 'available'),
        (v_clinic_id, v_prac_id, NULL, CURRENT_DATE + i, '15:30', '16:00', 'available'),
        (v_clinic_id, v_prac_id, NULL, CURRENT_DATE + i, '16:00', '16:30', 'available')
      ON CONFLICT DO NOTHING;
    END IF;
  END LOOP;
END $$;
