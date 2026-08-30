# Sokoni

**A voice-first financial operating system for informal businesses.**

Sokoni lets a trader talk naturally about what happened in their business and turns that
conversation into structured, auditable financial records.

> "Customer paid me 2,400 for two crates, but I still owe Jane 800 for tomatoes."

Sokoni is designed to read that as three separate business facts — a KES 2,400 sale, two
crates sold, and a KES 800 payable to Jane — record them correctly, and answer questions
about the resulting cash position in plain language.

It is not an expense tracker with a microphone attached. The ledger, the validation and
the arithmetic live in Django and PostgreSQL; the AI only proposes what to record.

---

## Status

| Phase | Status |
|-------|--------|
| B1 — Backend foundation | ✅ Complete |
| B2 — Authentication & users | ✅ Complete |
| B3 — Business profiles & tenancy | ✅ Complete |
| B4 — Parties & catalog | ✅ Complete |
| Everything after B4 | Planned (see roadmap) |

The project is built **one approved phase at a time**. Nothing below the "Planned" line
exists in the codebase yet, and this README marks planned work explicitly so it is never
mistaken for working functionality.

---

## Table of contents

- [Why Sokoni exists](#why-sokoni-exists)
- [What the product does](#what-the-product-does)
- [Architecture](#architecture)
- [Technology stack](#technology-stack)
- [Backend structure](#backend-structure)
- [Data model](#data-model)
- [AI and voice architecture](#ai-and-voice-architecture)
- [Security](#security)
- [Getting started](#getting-started)
- [Running the project](#running-the-project)
- [API reference](#api-reference)
- [Testing](#testing)
- [Environment variables](#environment-variables)
- [Project layout](#project-layout)
- [Development roadmap](#development-roadmap)
- [Academic evaluation](#academic-evaluation)
- [Deployment](#deployment)
- [Contributing workflow](#contributing-workflow)
- [Troubleshooting](#troubleshooting)

---

## Why Sokoni exists

Informal traders, freelancers and gig workers manage money through a mix of cash, mobile
money, credit and supplier relationships. Conventional accounting software assumes a
desk, a keyboard and an appetite for double-entry bookkeeping. Most of these businesses
have none of the three, so records live in a notebook or in someone's head.

Two consequences follow. Owners cannot answer "how much can I actually use right now?"
with confidence, and debts owed both ways are tracked informally until they are
forgotten or disputed.

Sokoni's premise is that **speaking is the lowest-friction way to record a transaction**.
A sale can be logged in the seconds after it happens, without stopping to fill a form.

---

## What the product does

### Financial management
Sales, income, purchases, expenses, cash position, profit estimation, summaries, and
full transaction history.

### Debt management
Sokoni treats debt as a first-class concept, not a variety of expense, and distinguishes:

- **Receivable** — money a customer owes the business
- **Payable** — money the business owes a supplier or person

with partial payments, running balances, due dates, status and aging.

### Cash and float intelligence
Informal businesses care less about accounting profit than about available float. Sokoni
is designed to answer:

```text
You currently have KES 8,500 available.
Customers owe you KES 4,200.
You have KES 6,000 in upcoming supplier obligations.
You may be short by roughly KES 1,300 tomorrow.
```

### Business intelligence
Rising expenses, falling revenue, unusual spending, repeated cash shortages, outstanding
debts and spending trends — communicated in ordinary language.

Calculated facts, estimates and AI suggestions are always labelled distinctly. Sokoni
must never present a guess as an accounting truth.

### Voice-first interaction
Voice is the primary interface; text is the fallback. The intended loop is: the user
speaks, Sokoni interprets, converts to structured events, validates, confirms when
uncertain, updates the ledger, and explains what it did.

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│  CLIENT — Next.js PWA (planned)                             │
│  Auth · Dashboard · Transactions · Debts · Insights         │
│  Microphone capture · Text fallback · Confirmation dialogs  │
└────────────┬───────────────────────────────┬────────────────┘
             │ HTTPS REST + JWT              │ Audio upload
             ▼                               ▼
┌────────────────────────────┐   ┌───────────────────────────┐
│  DJANGO API (DRF)          │   │  VOICE GATEWAY (planned)  │
│  Auth · Business · Ledger  │◄──│  STT → LLM extraction →   │
│  Debts · Finance · Agent   │   │  validate → tools → TTS   │
│  Audit · OpenAPI           │   └───────────┬───────────────┘
└────────────┬───────────────┘               │
             │ ORM                           │
             ▼                               ▼
┌────────────────────────────┐   ┌───────────────────────────┐
│  PostgreSQL                │   │  External AI services     │
│  Users · Businesses ·      │   │  ElevenLabs STT / TTS     │
│  Parties · Transactions ·  │   │  LLM (structured JSON)    │
│  Debts · Audit             │   └───────────────────────────┘
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│  Celery + Redis (planned)  │
│  Daily briefs · analysis · │
│  TTS jobs · reminders      │
└────────────────────────────┘
```

The governing rule:

```text
VOICE      is the interface.
AI         is the intelligence.
DJANGO     is the business logic.
POSTGRESQL is the source of truth.
```

The client and the AI **propose**; Django validates and commits. Sokoni must never
degrade into an LLM wrapped around a database.

---

## Technology stack

| Layer | Choice | Why |
|-------|--------|-----|
| Backend | Django 5 + DRF | Auth, ORM, permissions, admin, migrations in one coherent framework |
| Database | PostgreSQL 16 | Relational integrity for money; the ledger is not a document store |
| Auth | `djangorestframework-simplejwt` | Stateless tokens suit a separate PWA client |
| Async | Celery + Redis *(planned)* | Briefs, analysis and TTS must not block API requests |
| API docs | drf-spectacular *(planned)* | OpenAPI generated from the real serializers |
| Tests | pytest + pytest-django | Fast, fixture-driven, readable assertions |
| Frontend | Next.js + TypeScript + Tailwind *(planned)* | Mobile-first PWA consuming the REST API |
| Speech | ElevenLabs *(planned)* | STT and TTS, including a custom Sokoni voice |
| AI | LLM constrained to JSON tool calls *(planned)* | Extraction only — never database access |
| Deploy | Docker → Render *(planned)* | Web, worker, Redis and managed Postgres |

JSON columns are reserved for AI metadata and extraction traces. Structured financial
information is stored relationally.

---

## Backend structure

Sokoni is a **single Django project with focused apps** — not microservices. At this
scale, a monolith with clear internal boundaries is easier to reason about, test and
deploy.

| App | Responsibility | Status |
|-----|----------------|--------|
| `config` | Settings, URLs, WSGI/ASGI, environment loading | Built |
| `apps.core` | Health check, shared abstract models | Built |
| `apps.accounts` | User model, JWT lifecycle, profile | Built |
| `apps.businesses` | Business profiles, membership, tenant isolation | Built |
| `apps.parties` | Customers and suppliers | Built |
| `apps.catalog` | Lightweight products and units | Built |
| `apps.ledger` | Transactions and payment records | Planned |
| `apps.debts` | Receivables, payables, payments, aging | Planned |
| `apps.finance` | Cash position, summaries, float risk | Planned |
| `apps.insights` | Trends and alerts | Planned |
| `apps.agent` | Tool registry and confirmation workflow | Planned |
| `apps.voice` | Audio jobs, transcripts, TTS artifacts | Planned |
| `apps.audit` | Immutable trail of financial mutations | Planned |
| `apps.integrations` | M-Pesa and future channels | Planned |

Layering convention: **views stay thin**. Serializers validate shape, permissions decide
access, and domain services own the business rules. Money arithmetic belongs in
`apps.finance`, never in a React component.

---

## Data model

Built today:

```text
User                                    Business
  id (UUID)                               id (UUID)
  email (unique, login)                   name · business_type · currency
  full_name · phone_number                location · phone_number · description
  active_business ──────────────────────► is_active (archive flag)
  is_active · is_staff                    created_by
  date_joined · updated_at                created_at · updated_at

                    Membership
                      business ──► Business
                      user ──────► User
                      role (owner | member)
                      invited_by
                      unique (business, user)

Party                                   Product
  business ──► Business                   business ──► Business
  name (unique per business)              name (unique per business)
  party_type (customer|supplier|both)     unit · default_price
  phone_number · notes                    notes
  is_active (archive flag)                is_active (archive flag)
```

`Membership` is the tenancy boundary: a user reaches a business only through it,
and every financial model hangs off `Business`. `Party` and `Product` are the first
records to use `BusinessScopedModel`, the shared base that the ledger and debts will
also build on.

Planned shape once the ledger lands:

```text
User ──< Membership >── Business
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
      Party            Product          Transaction
   (customer /         (optional)      (sale · expense ·
    supplier)                           purchase · income ·
         │                              payment)
         │                 ▲                 │
         └──── Debt ───────┴─────────────────┘
              (receivable | payable)
                    │
              DebtPayment
                    │
              AuditEvent  ←── every financial mutation
```

Every transaction will carry a `source` field distinguishing `manual`, `voice`,
`import`, `api`, `system` and later `mpesa`. This drives both auditability and the
academic evaluation, which compares voice entry against form entry.

The model is **event-oriented rather than strict double-entry**. Full double-entry would
add rigour that this user base does not need and a vocabulary they do not use.

---

## AI and voice architecture

Not yet implemented. Documented here because it constrains everything built before it.

```text
User speaks
    ↓
Frontend captures audio
    ↓
Django voice endpoint
    ↓
Speech-to-text (ElevenLabs)
    ↓
Transcript
    ↓
LLM → structured intent JSON
    ↓
Django validates schema, business rules and confidence
    ↓
High confidence → execute tool        Low confidence → ask the user
    ↓
Domain service writes Transaction / Debt + AuditEvent
    ↓
Response text
    ↓
Text-to-speech (ElevenLabs)
    ↓
User hears the confirmation
```

### The non-negotiable rule

```text
FORBIDDEN:  LLM → raw SQL → database
REQUIRED:   LLM → structured intent → validation → service → database
```

Financial records must be deterministic and auditable. The LLM never receives database
credentials and cannot compose queries.

### Agent tools

The AI will choose from a fixed registry of backend-controlled operations: record
income, record expense, record sale, create receivable, create payable, record payment,
get balance, get cash position, get debts, get recent transactions, calculate summary,
check float risk, generate daily brief. The backend decides whether each call is allowed.

### Speech Sokoni must handle

English, Swahili, Sheng and code-switched speech, with informal money expressions:

```text
"Nimeuza tomatoes mbili for 1,500."
"Customer amesema atalipa kesho."
"John bado ananidai 2k."
"I bought stock ya 10k."
```

### Confirmation and safety

Uncertain interpretations are never committed silently:

```text
High confidence → "Recorded a KES 2,400 sale."
Low confidence  → "Did you say you received KES 24,000?"
```

---

## Security

Sokoni handles money, so security is a first-class requirement rather than a hardening
pass at the end.

**Implemented**

- Passwords hashed with Django's PBKDF2 defaults and validated on registration
- JWT access tokens (30 min) and refresh tokens (7 days)
- Refresh token **rotation** with blacklisting, so a leaked refresh token has a short life
- Explicit logout endpoint that blacklists the presented refresh token
- `IsAuthenticated` as the DRF default — endpoints are private unless they opt out
- **UUID primary keys on users**, so account identifiers cannot be guessed or enumerated
- `/auth/me/` resolves to `request.user`, ignoring any `id` supplied by the client
- Secrets read from environment variables; `.env` is git-ignored
- Production settings enforce a strong `SECRET_KEY`, explicit `ALLOWED_HOSTS`, HSTS,
  secure cookies and SSL redirect
- CORS restricted to an allowlist

- **Business-scoped querysets** — every business query goes through
  `Business.objects.for_user(request.user)`, so a foreign ID returns 404
- Role-based authorisation separating members from owners
- A business can never be left without an owner

**Planned**

- Rate limiting and throttling on auth and voice endpoints (B9)
- Audit logging of every financial mutation
- Confirmation gates before AI-driven writes

A user must never retrieve another business's financial data by changing an ID in a URL.
This is enforced with tests, not assumed.

---

## Getting started

### Prerequisites

- Python 3.12 or newer (3.13 tested)
- Docker Desktop — supplies PostgreSQL and Redis
- Git

### First-time setup

```bash
git clone https://github.com/captainblair/sokoni.git
cd sokoni

python -m venv .venv
```

Activate the virtual environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

Install dependencies and create your environment file:

```bash
pip install -r backend/requirements/local.txt
cp .env.example .env          # Windows: copy .env.example .env
```

Start the database and cache, then apply migrations:

```bash
docker compose up db redis -d
cd backend
python manage.py migrate
```

### Ports

Compose publishes Postgres and Redis on **non-default host ports** so they never collide
with a database already installed on your machine:

| Service | Host port | Container port |
|---------|-----------|----------------|
| PostgreSQL | 5433 | 5432 |
| Redis | 6380 | 6379 |
| API | 8000 | 8000 |

When Django runs outside Docker, `POSTGRES_PORT` must be `5433`.

Prefer a PostgreSQL installed directly on your machine? Set `POSTGRES_PORT=5432` in
`.env` and create the role and database once with `scripts/create_local_db.sql` (requires
your postgres superuser password).

---

## Running the project

### Everyday development

```bash
docker compose up db redis -d     # only after a reboot
cd backend
python manage.py runserver
```

- Health check: http://127.0.0.1:8000/api/v1/health/
- Admin: http://127.0.0.1:8000/admin/

Create an admin account (it prompts for an **email**, not a username):

```bash
python manage.py createsuperuser
```

### Fully containerised

```bash
docker compose up --build
```

This runs migrations and serves the API through Gunicorn.

### SQLite smoke mode

For a quick check with no database container, set `DATABASE_ENGINE=sqlite` in `.env`.
Useful offline; use PostgreSQL for real work, since that is what production runs.

---

## API reference

Base URL: `/api/v1/`. Authenticated requests send `Authorization: Bearer <access token>`.

### Health

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/v1/health/` | public | Liveness and database connectivity |

Returns `200` with `{"status": "ok", "database": "up"}`, or `503` when the database is
unreachable. Add `?verbose=1` to include the connection error.

### Authentication

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/v1/auth/register/` | public | Create an account, returns a token pair |
| POST | `/api/v1/auth/login/` | public | Obtain access and refresh tokens |
| POST | `/api/v1/auth/refresh/` | public | Exchange a refresh token for a new access token |
| POST | `/api/v1/auth/verify/` | public | Check whether a token is valid |
| POST | `/api/v1/auth/logout/` | required | Blacklist a refresh token |
| GET | `/api/v1/auth/me/` | required | Read your own profile |
| PATCH | `/api/v1/auth/me/` | required | Update `full_name` or `phone_number` |
| POST | `/api/v1/auth/password/change/` | required | Change your password |

**Register**

```json
POST /api/v1/auth/register/
{
  "email": "trader@example.com",
  "full_name": "Amina Trader",
  "phone_number": "+254712345678",
  "password": "Sokoni-Pass-2026",
  "password_confirm": "Sokoni-Pass-2026"
}
```

```json
201 Created
{
  "user": {
    "id": "c051f32d-831f-4ba6-bc7d-2da387d16fd8",
    "email": "trader@example.com",
    "full_name": "Amina Trader",
    "phone_number": "+254712345678",
    "date_joined": "2026-08-30T18:04:11.512Z"
  },
  "access": "eyJhbGciOi...",
  "refresh": "eyJhbGciOi..."
}
```

Emails are stored lowercase, so login is case-insensitive. Passwords run through
Django's validators and are never returned in any response.

**Try it from PowerShell**

```powershell
$body = @{
  email = "you@example.com"
  full_name = "Your Name"
  password = "Sokoni-Pass-2026"
  password_confirm = "Sokoni-Pass-2026"
} | ConvertTo-Json

$auth = Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/auth/register/ `
  -Method Post -ContentType "application/json" -Body $body

Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/auth/me/ `
  -Headers @{ Authorization = "Bearer $($auth.access)" }
```

### Businesses

All endpoints require authentication and are scoped to the businesses you belong to.

| Method | Path | Role | Purpose |
|--------|------|------|---------|
| GET | `/api/v1/businesses/` | member | List your businesses |
| POST | `/api/v1/businesses/` | — | Create a business; you become its owner |
| GET | `/api/v1/businesses/{id}/` | member | Retrieve one business |
| PATCH | `/api/v1/businesses/{id}/` | owner | Update details |
| DELETE | `/api/v1/businesses/{id}/` | owner | Archive (never hard-deleted) |
| POST | `/api/v1/businesses/{id}/activate/` | member | Set your working business |
| GET | `/api/v1/businesses/active/` | — | Your currently selected business |
| GET | `/api/v1/businesses/{id}/members/` | member | List members |
| POST | `/api/v1/businesses/{id}/members/` | owner | Add a member by email |
| PATCH | `/api/v1/businesses/{id}/members/{membership_id}/` | owner | Change a role |
| DELETE | `/api/v1/businesses/{id}/members/{membership_id}/` | owner | Remove a member |

**Create a business**

```json
POST /api/v1/businesses/
{
  "name": "Amina Groceries",
  "business_type": "retail",
  "location": "Gikomba",
  "phone_number": "+254712345678"
}
```

```json
201 Created
{
  "id": "6f1d…",
  "name": "Amina Groceries",
  "business_type": "retail",
  "currency": "KES",
  "location": "Gikomba",
  "my_role": "owner",
  "member_count": 1,
  "created_at": "2026-08-30T18:20:04.113Z"
}
```

Business types: `retail`, `market_vendor`, `food`, `services`, `transport`,
`freelance`, `agriculture`, `other`.

**Rules enforced by the backend**

- Requesting a business you do not belong to returns **404**, not 403 — a foreign
  record is never confirmed to exist
- Members can read; only owners can update, archive or manage membership
- A business can never lose its last owner, by removal or demotion
- Archiving sets `is_active = false` and clears it from anyone's active selection
- Your first business becomes your active business automatically

### Parties and products

Both resources belong to a single business. The business is taken from your **active
business** unless you send an explicit `business` value, so voice commands — which never
name a business — work without extra ceremony.

| Method | Path | Purpose |
|--------|------|---------|
| GET / POST | `/api/v1/parties/` | List or create customers and suppliers |
| GET / PATCH / DELETE | `/api/v1/parties/{id}/` | Retrieve, update, archive |
| GET / POST | `/api/v1/products/` | List or create products |
| GET / PATCH / DELETE | `/api/v1/products/{id}/` | Retrieve, update, archive |

Shared query parameters:

| Parameter | Applies to | Effect |
|-----------|-----------|--------|
| `business` | both | Target a specific business you belong to |
| `search` | both | Case-insensitive match on name (and phone or unit) |
| `include_archived=true` | both | Include archived records |
| `type` | parties | `customer` or `supplier` |

**Create a customer**

```json
POST /api/v1/parties/
{
  "name": "Mary Wanjiku",
  "party_type": "customer",
  "phone_number": "+254712345678"
}
```

Party types are `customer`, `supplier` or `both`. A trader who buys from you and also
supplies you is **one record**, because in a later phase their receivable and payable
balances have to net against each other.

**Create a product**

```json
POST /api/v1/products/
{
  "name": "Soda crate",
  "unit": "crate",
  "default_price": "1200.00"
}
```

`default_price` is a suggestion, never an enforced rate — informal prices move daily.

**Rules enforced by the backend**

- Names are unique per business, compared case-insensitively, so a spoken "jane" cannot
  create a duplicate of an existing "Jane"
- The same name may exist in different businesses
- Records are archived rather than deleted
- Records in another business return **404** on every operation

An interactive OpenAPI/Swagger schema arrives in phase B9.

---

## Testing

```bash
cd backend
pytest
```

Currently **96 tests**, running in about 5 seconds:

| Area | Coverage |
|------|----------|
| Health | Endpoint stays public and reports database state |
| Registration | Validation, email normalisation, duplicates, weak passwords |
| Authentication | Login, refresh, verify, logout blacklisting, inactive accounts |
| Profile | Self-only updates, password change |
| Businesses | Creation, ownership, archiving, active-business context |
| **Isolation** | Foreign businesses and records return 404 on every operation |
| Membership | Adding by email, role changes, last-owner protection |
| Parties | Types, duplicate names, filtering, search, archiving |
| Catalog | Prices, duplicates, search, archiving |

Useful variations:

```bash
pytest -v                                   # verbose
pytest tests/test_businesses_isolation.py   # one module
pytest -k "isolation"                       # match by name
pytest --create-db                          # rebuild the test database
```

Tests run under `config/settings/test.py`, which uses a fast password hasher and reuses
the test database. Your development data is never touched.

Testing expands with each phase: financial calculation fixtures in B7 and AI extraction
accuracy during the voice phases.

---

## Environment variables

Copy `.env.example` to `.env` and adjust. **Never commit `.env`.**

| Variable | Default | Purpose |
|----------|---------|---------|
| `DJANGO_ENV` | `local` | Selects the settings module (`local` / `production`) |
| `DJANGO_SECRET_KEY` | dev placeholder | Cryptographic signing; must be strong in production |
| `DJANGO_DEBUG` | `true` locally | Never enable in production |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Required in production |
| `DJANGO_TIME_ZONE` | `Africa/Nairobi` | Affects daily summaries and reporting |
| `DATABASE_ENGINE` | `postgresql` | Use `sqlite` only for offline smoke tests |
| `POSTGRES_DB` / `_USER` / `_PASSWORD` | `sokoni` | Database credentials |
| `POSTGRES_HOST` | `localhost` | `db` inside Docker Compose |
| `POSTGRES_PORT` | `5433` | Port Django connects to |
| `POSTGRES_HOST_PORT` | `5433` | Host port the container publishes |
| `REDIS_URL` | `redis://localhost:6380/0` | Reserved for Celery |
| `JWT_ACCESS_MINUTES` | `30` | Access token lifetime |
| `JWT_REFRESH_DAYS` | `7` | Refresh token lifetime |
| `JWT_SIGNING_KEY` | empty | Falls back to `DJANGO_SECRET_KEY` |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | Frontend origins |
| `WEB_PORT` | `8000` | Compose API port |

Reserved for later phases and intentionally unset: `ELEVENLABS_API_KEY`, `LLM_API_KEY`,
`MPESA_CONSUMER_KEY`, `MPESA_CONSUMER_SECRET`.

---

## Project layout

```text
sokoni/
├── backend/
│   ├── apps/
│   │   ├── core/              # Health check, shared abstract models
│   │   │   ├── constants.py   # Money precision conventions
│   │   │   ├── models.py      # UUID, timestamp and business-scoped bases
│   │   │   ├── viewsets.py    # BusinessScopedViewSet — tenancy in one place
│   │   │   ├── urls.py
│   │   │   └── views.py
│   │   ├── accounts/          # User model and JWT authentication
│   │   │   ├── admin.py
│   │   │   ├── managers.py
│   │   │   ├── migrations/
│   │   │   ├── models.py
│   │   │   ├── serializers.py
│   │   │   ├── urls.py
│   │   │   └── views.py
│   │   ├── businesses/        # Business profiles and tenancy
│   │   │   ├── admin.py
│   │   │   ├── migrations/
│   │   │   ├── models.py      # Business, Membership
│   │   │   ├── permissions.py # IsBusinessMember, IsBusinessOwner
│   │   │   ├── serializers.py
│   │   │   ├── services.py    # Business rules kept out of views
│   │   │   ├── urls.py
│   │   │   └── views.py
│   │   ├── parties/           # Customers and suppliers
│   │   └── catalog/           # Products and units
│   ├── config/
│   │   ├── settings/
│   │   │   ├── base.py        # Shared configuration
│   │   │   ├── local.py       # Development overrides
│   │   │   ├── test.py        # Fast hashing for the test suite
│   │   │   └── production.py  # Hardened production settings
│   │   ├── urls.py
│   │   ├── asgi.py
│   │   └── wsgi.py
│   ├── requirements/
│   │   ├── base.txt
│   │   ├── local.txt
│   │   └── production.txt
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_accounts_auth.py
│   │   ├── test_accounts_profile.py
│   │   ├── test_accounts_registration.py
│   │   ├── test_businesses_active_context.py
│   │   ├── test_businesses_crud.py
│   │   ├── test_businesses_isolation.py
│   │   ├── test_businesses_membership.py
│   │   ├── test_catalog.py
│   │   ├── test_health.py
│   │   ├── test_parties.py
│   │   └── test_parties_isolation.py
│   ├── Dockerfile
│   ├── manage.py
│   └── pytest.ini
├── scripts/
│   └── create_local_db.sql    # Bootstrap a locally installed PostgreSQL
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## Development roadmap

Each phase is planned, approved, implemented, tested and reviewed before the next begins.

### Backend

| Phase | Objective | Status |
|-------|-----------|--------|
| B1 | Runnable Django project, Docker, Postgres, health check, pytest | ✅ Complete |
| B2 | Custom user model and full JWT lifecycle | ✅ Complete |
| B3 | Business profiles, membership, tenant isolation | ✅ Complete |
| B4 | Parties (customers/suppliers) and a light product catalog | ✅ Complete |
| B5 | Financial ledger — transactions, methods, statuses, `source` | Next |
| B6 | Debt management — receivables, payables, partial payments, aging | Planned |
| B7 | Financial intelligence — cash position, summaries, float risk | Planned |
| B8 | Agent tool contracts and confirmation model (no LLM yet) | Planned |
| B9 | OpenAPI docs, rate limiting, audit coverage, full regression suite | Planned |

### Frontend

| Phase | Objective |
|-------|-----------|
| F0 | Map endpoints to screens and design the frontend architecture |
| F1 | Next.js + TypeScript + Tailwind foundation and typed API client |
| F2 | Authentication screens |
| F3 | Dashboard — available, owed, owing, today's activity, alerts |
| F4 | Transaction recording and history |
| F5 | Debt management |
| F6 | Financial insights |
| F7 | PWA and mobile polish |
| F8 | Frontend testing |

### Voice and AI

| Phase | Objective |
|-------|-----------|
| V0 | ElevenLabs setup, voice training guide, cost analysis, schemas |
| V1 | Audio capture and upload |
| V2 | Speech-to-text |
| V3 | LLM intent extraction to structured JSON |
| V4 | Mapping intents onto agent tools and the ledger |
| V5 | Confidence scoring, confirmation, duplicate prevention |
| V6 | Text-to-speech with a custom Sokoni voice |
| V7 | Conversational agent loop |
| V8 | Daily spoken brief via Celery |
| V9 | End-to-end voice testing and the evaluation harness |

### Final

| Phase | Objective |
|-------|-----------|
| Z1 | End-to-end integration testing |
| Z2 | Security review |
| Z3 | Performance |
| Z4 | Docker and Render deployment |
| Z5 | Evaluation dataset and measured metrics |
| Z6 | Academic documentation |

### Explicitly deferred

M-Pesa reconciliation, WhatsApp as a channel, deep inventory management, chama group
finance, and anomaly detection. The architecture reserves space for them — `source` on
transactions and the `integrations` app boundary — but none are MVP scope.

---

## Academic evaluation

Sokoni is also a research artifact. Three evaluation strands are planned, and **no
metric will be reported before it has actually been measured**.

**Human-computer interaction.** Voice-first entry compared against traditional form
entry, measuring time to record a transaction, number of interactions, completion rate,
error rate and user satisfaction. The `source` field on every transaction makes this
comparison possible from real usage data.

**Natural language processing.** Accuracy of intent classification, amount extraction,
person and product extraction, date extraction and end-to-end record correctness.

**Code-switching.** Performance across English, Swahili, Sheng and mixed utterances — the
way the target users actually speak.

An evaluation dataset of roughly 100–200 realistic utterances with expected structured
output will be built during the voice phases:

```text
Input:    "I sold two crates for 2400."
Expected: intent=SALE · amount=2400 · quantity=2 · product=crates · payment=PAID

Input:    "Nimeuza tomatoes 2k lakini customer atalipa kesho."
Expected: intent=SALE · amount=2000 · product=tomatoes · payment=CREDIT
```

---

## Deployment

Target platform: **Render**, using Docker.

Planned topology: a web service running Gunicorn, a Celery worker, a managed PostgreSQL
instance and Redis. Production settings already enforce a strong secret key, explicit
allowed hosts, HSTS, secure cookies and SSL redirect; static files are served by
WhiteNoise.

Deployment is phase Z4 and has not been performed yet.

---

## Contributing workflow

Development follows a strict cycle:

```text
plan → approve → implement → test → explain → review → approve → next phase
```

No phase begins before the previous one is reviewed, and future features are never
implemented early "because they might be useful".

Commits are meaningful units of work, not per-file noise:

```text
feat: establish django backend foundation
feat: implement authentication and user accounts
feat: add business profiles
test: add ledger test suite
```

Before committing, run `git status` and confirm `.env` is excluded while `.env.example`
is included.

---

## Troubleshooting

**`password authentication failed for user "sokoni"`**
Django is reaching a PostgreSQL other than Sokoni's container — usually one installed
locally on port 5432. Confirm `POSTGRES_PORT=5433` in `.env`.

**`connection refused` on port 5433**
The containers are not running. Start them with `docker compose up db redis -d`.

**`ModuleNotFoundError: No module named 'django'`**
The virtual environment is not active. Re-run the activate command; your prompt should
begin with `(.venv)`.

**`docker compose` cannot reach the Docker daemon**
Docker Desktop is not running. Start it and wait for the whale icon to settle.

**Port 8000 already in use**
Run on another port: `python manage.py runserver 8001`.

---

## License

Academic project. License to be determined.
