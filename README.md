# MediBook — Divine Comfort Clinic

**WhatsApp Appointment Booking for Divine Comfort Clinic — Harare, Zimbabwe**

MediBook powers WhatsApp-based appointment booking for Divine Comfort Clinic. Patients message the clinic’s WhatsApp number to book appointments, pay via EcoCash, and receive automated reminders.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.12) |
| Database | Supabase (PostgreSQL with RLS) |
| WhatsApp | Twilio WhatsApp Business API |
| Payments | EcoCash API (Zimbabwe) |
| Session State | Supabase `conversation_sessions` table |
| Background Jobs | Vercel Cron Jobs |
| Admin Auth | Supabase Auth (JWT) |
| Deployment | Vercel (serverless) |

## Project Structure

```
medibook/
├── api/index.py                    # Vercel entry point
├── app/
│   ├── main.py                     # FastAPI app factory
│   ├── config.py                   # Pydantic Settings
│   ├── dependencies.py             # FastAPI DI
│   ├── modules/
│   │   ├── webhook/                # Twilio webhook handler
│   │   ├── flow/                   # Conversation state machine
│   │   ├── clinics/                # Clinic CRUD
│   │   ├── bookings/               # Slots & appointments
│   │   ├── payments/               # EcoCash integration
│   │   ├── reminders/              # Appointment reminders
│   │   └── patients/               # Patient records
│   ├── core/                       # Exceptions, logging, security
│   └── db/                         # Supabase client & migrations
├── vercel.json
├── requirements.txt
├── .env.example
└── README.md
```

## Quick Start

### 1. Clone & Setup

```bash
python -m venv venv
# Windows
.\venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your actual credentials
```

### 3. Run Database Migrations

Execute the SQL scripts in `app/db/migrations/` in order in the Supabase SQL Editor:
1. `001_initial_schema.sql`
2. `002_rls_policies.sql`
3. `003_indexes.sql`
4. `004_seed_divine_comfort.sql` — seeds the clinic, services, practitioner, and sample slots

### 4. Run Locally

```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Deploy to Vercel

```bash
vercel --prod
```

## Core Patient Flow

1. Patient messages the clinic's WhatsApp number
2. Bot presents a branded menu: Book Appointment / View Slots / FAQs
3. Patient selects service and time slot
4. Patient pays a booking fee via EcoCash
5. System confirms booking and schedules a 24-hour reminder

## Conversation States

| State | Description |
|-------|------------|
| `IDLE` | Waiting for first message — shows greeting + menu |
| `SELECTING_SERVICE` | Patient choosing a service |
| `SELECTING_SLOT` | Patient choosing a time slot |
| `CONFIRMING_DETAILS` | Patient reviewing booking summary |
| `AWAITING_PAYMENT` | EcoCash payment being initiated |
| `PAYMENT_PROCESSING` | Waiting for EcoCash confirmation |

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | None | Health check |
| `POST` | `/webhook/twilio` | Twilio Signature | Inbound WhatsApp messages |
| `POST` | `/payments/ecocash/callback` | None | EcoCash payment notifications |
| `GET` | `/clinic/` | JWT | Get clinic details |
| `PATCH` | `/clinic/` | JWT | Update clinic details |
| `GET` | `/clinic/services` | JWT | List services |
| `POST` | `/clinic/services` | JWT | Create service |
| `GET` | `/bookings/slots` | JWT | List available slots |
| `POST` | `/bookings/slots` | JWT | Create slot |
| `POST` | `/bookings/slots/bulk` | JWT | Create slots in bulk |
| `GET` | `/bookings/appointments` | JWT | List appointments |
| `GET` | `/jobs/send-reminders` | Cron Secret | Send due reminders |
| `GET` | `/jobs/expire-payments` | Cron Secret | Expire stale payments |
| `GET` | `/jobs/expire-sessions` | Cron Secret | Clean expired sessions |

## Security

- **Twilio Signature Validation** on all webhook requests
- **JWT Authentication** on all admin endpoints
- **Cron Secret** on all `/jobs/*` endpoints
- **Row Level Security** on all Supabase tables
- **clinic_id isolation** enforced at the repository layer
- **PII masking** in all structured logs
- **Rate limiting** — 20 messages per 5 minutes per patient

## EcoCash Sandbox

- Sandbox PIN codes: `0000`, `1234`, `9999`
- Sandbox endpoint: `/api/v2/payment/instant/c2b/sandbox`

---

*MediBook · Divine Comfort Clinic · Built for Zimbabwe · Production-Ready from Day One*
