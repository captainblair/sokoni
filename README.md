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
| B5 — Financial ledger | ✅ Complete |
| B6 — Debt management | ✅ Complete |
| B7 — Financial intelligence | ✅ Complete |
| B8 — Agent tools & confirmation | ✅ Complete |
| Everything after B8 | Planned (see roadmap) |

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
answers:

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
| `apps.ledger` | Transactions and payment records | Built |
| `apps.debts` | Receivables, payables, payments, aging | Built |
| `apps.finance` | Cash position, summaries, float risk | Built |
| `apps.insights` | Trends and alerts | Planned |
| `apps.agent` | Tool registry and confirmation workflow | Built |
| `apps.voice` | Audio jobs, transcripts, TTS artifacts | Planned |
| `apps.audit` | Immutable trail of financial mutations | Planned |
| `apps.integrations` | M-Pesa and future channels | Planned |

Layering convention: **views stay thin**. Serializers validate shape, permissions decide
access, and domain services own the business rules. Money arithmetic belongs in
`apps.finance`, never in a React component.

Two module names carry that split consistently: a `services.py` is the only place a model
is written, and a `selectors.py` is the only place numbers are derived from what is
already there.

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

                 Transaction
                   business ──► Business
                   party ─────► Party      (nullable)
                   product ───► Product    (nullable)
                   transaction_type (sale|income|purchase|expense)
                   amount · amount_paid · currency
                   payment_status · payment_method
                   quantity · unit_price
                   occurred_at · description · notes
                   source · reference · created_by
                   is_active (archive flag)

                 Debt                            DebtPayment
                   business ──► Business           debt ──► Debt
                   party ─────► Party              amount · paid_at
                   debt_type (receivable|payable)  payment_method
                   original_amount · amount_paid   notes · source
                   status · due_date               created_by
                   source_transaction ──► Transaction (nullable, one-to-one)
                   description · notes · source
                   is_active (archive flag)

                 PendingAction
                   business ──► Business
                   user ──────► User
                   token · tool · parameters
                   question · reason · confidence
                   expires_at · consumed_at
```

`Membership` is the tenancy boundary: a user reaches a business only through it,
and every financial model hangs off `Business`. `Party`, `Product`, `Transaction` and
`Debt` all use `BusinessScopedModel`, the shared base that carries the business link and
the archive flag.

`Debt` and `Transaction` describe the same obligation from two angles, so the link between
them is deliberately one-directional: the debt owns the settlement history, and the
transaction mirrors it.

Planned shape once the remaining models land:

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

Every transaction carries a `source` field distinguishing `manual`, `voice`, `import`,
`api`, `system` and later `mpesa`. This drives both auditability and the academic
evaluation, which compares voice entry against form entry.

The model is **event-oriented rather than strict double-entry**. Full double-entry would
add rigour that this user base does not need and a vocabulary they do not use.

---

## AI and voice architecture

The **tool registry and confirmation workflow are built**. Speech-to-text, the LLM and
ElevenLabs are not: those arrive in the voice phases. What exists now is the door an AI
will have to walk through, so that when a model is attached it cannot invent a new way
into the books.

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
- A fixed agent tool registry: the only operations an AI may name
- Confirmation gates on writes that are uncertain, unusually large, or name a stranger
- Confirmation tokens bound to the user and business that raised them, single-use, expiring

**Planned**

- Rate limiting and throttling on auth and voice endpoints (B9)
- Audit logging of every financial mutation

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

### Transactions

The ledger. Scoped to a business exactly like parties and products.

| Method | Path | Purpose |
|--------|------|---------|
| GET / POST | `/api/v1/transactions/` | List or record transactions |
| GET / PATCH / DELETE | `/api/v1/transactions/{id}/` | Retrieve, correct, archive |

**Record a sale**

```json
POST /api/v1/transactions/
{
  "transaction_type": "sale",
  "quantity": "2",
  "unit_price": "1200.00",
  "party": "<customer id>",
  "product": "<product id>",
  "payment_method": "mpesa",
  "description": "Two crates of soda"
}
```

```json
201 Created
{
  "transaction_type": "sale",
  "amount": "2400.00",
  "amount_paid": "2400.00",
  "outstanding_amount": "0.00",
  "signed_amount": "2400.00",
  "payment_status": "paid",
  "currency": "KES",
  "source": "manual"
}
```

`amount` may be omitted when `quantity` and `unit_price` are given — "two crates at
1,200" is how a sale gets spoken, so the total is derived rather than demanded.

**Record something bought on credit**

```json
POST /api/v1/transactions/
{
  "transaction_type": "purchase",
  "amount": "800.00",
  "party": "<supplier id>",
  "payment_status": "credit",
  "description": "Tomatoes"
}
```

Because a supplier is named and the money is still owed, the backend also opens a **debt**
against Jane automatically. Settling it happens through that debt (see below), and the
transaction's `payment_status` and `outstanding_amount` follow along.

A credit transaction with no party stays a plain unsettled transaction: with nobody named
there is nobody to chase, so no debt is created and `amount_paid` can be patched directly.

**Vocabulary**

| Field | Values |
|-------|--------|
| `transaction_type` | `sale`, `income`, `purchase`, `expense` |
| `payment_status` | `paid`, `partial`, `credit` |
| `payment_method` | `cash`, `mpesa`, `bank`, `credit`, `other` |
| `source` | `manual`, `voice`, `import`, `api`, `system`, `mpesa` |

`sale` and `income` bring money in; `purchase` and `expense` take it out, which is what
`signed_amount` reflects.

**Filters**

| Parameter | Effect |
|-----------|--------|
| `type`, `status`, `method`, `source` | Match that field |
| `party`, `product` | Transactions involving one record |
| `unsettled=true` | Anything still owed in either direction |
| `date_from`, `date_to` | ISO 8601 range on `occurred_at` |
| `search` | Description, notes or reference |
| `business`, `include_archived` | As for parties and products |

**Rules enforced by the backend**

- Amounts must be positive, and `amount_paid` can never exceed `amount`
- Payment status and amount paid must agree; a contradiction is rejected rather than
  silently corrected
- A transaction cannot be dated in the future
- A party or product from another business cannot be attached
- Currency always follows the business
- Transactions are archived, never deleted
- A transaction whose settlement is tracked as a debt rejects direct `amount_paid` edits

### Debts

Credit is how informal trade actually works, so debt is a first-class record rather than a
transaction with a flag. A debt is an obligation in one direction: a **receivable** is
money owed to the business, a **payable** is money the business owes.

| Method | Path | Purpose |
|--------|------|---------|
| GET / POST | `/api/v1/debts/` | List or record debts |
| GET / PATCH / DELETE | `/api/v1/debts/{id}/` | Retrieve, amend, archive |
| GET / POST | `/api/v1/debts/{id}/payments/` | Payment history, or record an instalment |
| POST | `/api/v1/debts/{id}/write-off/` | Mark as uncollectable |

**Where debts come from**

Most debts are never typed in. Recording a credit or partly paid transaction against a
named party opens the matching debt automatically — a credit sale becomes a receivable, a
credit purchase becomes a payable — so "I sold Mary sugar, she'll pay Friday" is one
sentence, not two records.

A debt can also be recorded on its own, for money owed from before the business started
using Sokoni:

```json
POST /api/v1/debts/
{
  "debt_type": "receivable",
  "party": "<customer id>",
  "original_amount": "800.00",
  "due_date": "2026-09-05",
  "description": "Sugar taken on credit"
}
```

**Record a payment**

```json
POST /api/v1/debts/{id}/payments/
{ "amount": "500.00", "payment_method": "mpesa" }
```

```json
GET /api/v1/debts/{id}/
{
  "original_amount": "800.00",
  "amount_paid": "500.00",
  "balance": "300.00",
  "status": "partial",
  "days_overdue": 0,
  "aging_bucket": "current",
  "payments": [{ "amount": "500.00", "payment_method": "mpesa", "paid_at": "..." }]
}
```

Every instalment is kept, so a trader can see that Mary paid 500 on Monday and 300 on
Thursday rather than only a shrinking balance.

**Vocabulary**

| Field | Values |
|-------|--------|
| `debt_type` | `receivable`, `payable` |
| `status` | `open`, `partial`, `settled`, `written_off` |
| `aging_bucket` | `current`, `1-7`, `8-30`, `31-60`, `60+` |

`status` is derived from the amounts and never set by hand. `aging_bucket` and
`days_overdue` are computed from `due_date`, and a settled debt is never overdue.

**Filters**

| Parameter | Effect |
|-----------|--------|
| `type`, `status`, `party` | Match that field |
| `outstanding=true` | Only debts with money still to move |
| `overdue=true` | Outstanding and past the due date |
| `due_before` | Falling due on or before a date |
| `search` | Description, notes or party name |
| `business`, `include_archived` | As for parties and products |

Debts are listed by due date, so the most pressing obligation is first.

**Rules enforced by the backend**

- A debt always names a party; there is no such thing as an anonymous debt
- A payment can never exceed the outstanding balance
- A settled or written-off debt takes no further payment
- Paying a debt updates the transaction it came from, so revenue is never counted twice
- A debt created from a transaction is amended by correcting that transaction, and the
  correction cannot fall below what has already been paid

### Finance

Four read-only reports. Nothing here is stored — a cash position saved to a column is a
cash position that will eventually disagree with the transactions behind it.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/finance/cash-position/` | What is in hand and what is owed either way |
| GET | `/api/v1/finance/summary/` | Revenue, costs and cash movement over a period |
| GET | `/api/v1/finance/float-risk/` | Whether upcoming obligations can be met |
| GET | `/api/v1/finance/daily-brief/` | All of the above, in sentences |

**Two different questions**

*Accrual* asks what the business earned: a sale is revenue the moment it happens, paid or
not. *Cash* asks what the business can actually spend today. Informal traders live by the
second and are judged by the first, so both are reported and never blended — `revenue` and
`profit_estimate` are accrual, `cash_in`, `cash_out` and `available_cash` are cash.

**Cash position**

```json
GET /api/v1/finance/cash-position/
{
  "available_cash": "8500.00",
  "cash_in": "9000.00",
  "cash_out": "500.00",
  "receivables": "4200.00",
  "receivables_overdue": "0.00",
  "payables": "6000.00",
  "projected_cash": "6700.00"
}
```

`available_cash` counts only money that actually moved: amounts settled on transactions,
plus payments against debts that were entered on their own. A debt created from a credit
sale mirrors its payments back onto that transaction, so counting both would double the
money. `receivables` and `payables` include credit transactions recorded without naming
anyone — nobody to chase, but the money is owed all the same.

**Summary**

```json
GET /api/v1/finance/summary/?period=month
```

| Parameter | Values |
|-----------|--------|
| `period` | `today` (default), `yesterday`, `week`, `month`, `year`, `all` |
| `date_from`, `date_to` | An explicit range, in place of `period` |

`week` means the last seven days rather than the calendar week, because a trader asking
"how was this week" means the days just lived through. Alongside the totals, `by_type`
groups on amount billed, while `by_payment_method` groups on what was actually settled: a
credit sale has no payment method yet, and counting it as cash would describe money that
never arrived.

`profit_estimate` is revenue less costs and is named an estimate deliberately. There is no
stock valuation, depreciation or owner's drawings in this model, and dressing the number
up as an audited profit would be a lie of exactly the kind Sokoni is meant to avoid.

**Float risk**

The question that actually matters day to day. A profitable week is no comfort if the
supplier arrives on Tuesday and the money is in other people's pockets.

```json
GET /api/v1/finance/float-risk/?days=7
{
  "available_cash": "1000.00",
  "obligations_due": "2500.00",
  "expected_receipts": "3000.00",
  "shortfall": "1500.00",
  "risk_level": "watch"
}
```

| Level | Meaning |
|-------|---------|
| `none` | Cash on hand covers everything falling due |
| `watch` | Covered only if customers pay on time — the assumption traders get burnt by |
| `high` | Short even if everyone who owes pays |

Overdue obligations always count as due. Debts nobody put a date on are reported separately
as `undated_payables` and `undated_receivables` rather than folded into the window, because
"sometime" is not a plan.

**Daily brief**

The numbers said back in ordinary language, assembled from the reports above. No AI is
involved: the voice layer in a later phase reads these lines rather than inventing its own.

```json
GET /api/v1/finance/daily-brief/
{
  "headline": "You have KES 8,500 available.",
  "messages": [
    { "kind": "fact", "text": "You have KES 8,500 available." },
    { "kind": "fact", "text": "Today you took in KES 9,000 and spent KES 500 across 3 entries." },
    { "kind": "fact", "text": "Customers owe you KES 4,200." },
    { "kind": "estimate", "text": "You may be short by about KES 1,500 in the next 7 days, unless the KES 3,000 owed to you comes in first." }
  ]
}
```

Every line is tagged `fact` or `estimate`. A number that came from arithmetic on recorded
transactions and a number that depends on customers behaving as promised are not the same
kind of claim, and a trader deciding whether to buy stock tomorrow deserves to know which
one they are hearing. The full `cash_position`, `today` and `float_risk` objects are
returned alongside the sentences.

All four accept `business` to report on a specific business, and otherwise use the active
one.

### Agent

The one door an AI is allowed through. There is no language model here: a tool is callable
by a test, a script or a form in exactly the same way, which is what makes the layer
verifiable on its own.

```text
FORBIDDEN:  LLM → raw SQL → database
REQUIRED:   LLM → structured intent → validation → service → database
```

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/agent/tools/` | The published contract: names, parameters, which writes |
| POST | `/api/v1/agent/execute/` | Run one tool, or redeem a confirmation |

**The tools**

| Name | Writes? | What it does |
|------|---------|--------------|
| `record_sale` | yes | Something sold, paid now or taken on credit |
| `record_income` | yes | Money received that is not a sale of goods |
| `record_purchase` | yes | Stock or goods bought for the business |
| `record_expense` | yes | Money spent running the business |
| `create_receivable` | yes | Someone owes the business |
| `create_payable` | yes | The business owes someone |
| `record_debt_payment` | yes | An instalment against a named party's debt |
| `get_cash_position` | no | What is in hand and what is owed |
| `get_summary` | no | Revenue, costs and cash over a period |
| `get_debts` | no | Outstanding receivables and payables |
| `get_party_balance` | no | Where one person stands |
| `get_recent_transactions` | no | The latest ledger entries |
| `check_float_risk` | no | Whether upcoming obligations can be met |
| `get_daily_brief` | no | The whole picture, in sentences |

Every write goes through the same domain service the REST API uses. A spoken sale is
validated exactly like a typed one; there is no second, weaker path into the ledger.
Spoken names are resolved to records: one clear match is used, several matches is a
question, and no match at all is a new record — because a customer who has never been
written down is the normal case for a business that has only ever used a notebook.

**Record a sale**

```json
POST /api/v1/agent/execute/
{
  "tool": "record_sale",
  "parameters": {
    "amount": "2400.00",
    "party": "Mary Wanjiku",
    "payment_status": "credit"
  },
  "confidence": 0.92
}
```

```json
201 Created
{
  "status": "executed",
  "message": "Recorded a sale of KES 2,400 to Mary Wanjiku, with KES 2,400 still owed."
}
```

**When Sokoni stops to ask**

Reads are never confirmed. Writes are confirmed when the interpretation is shaky:

| Reason | When |
|--------|------|
| `low_confidence` | Reported confidence is below the threshold (default 0.75) |
| `unusual_amount` | The amount is several times this business's typical transaction |
| `new_party` | Nobody by that name has traded here before |

```json
200 OK
{
  "status": "confirmation_required",
  "message": "Did you mean a sale of KES 2,400?",
  "confirmation": {
    "token": "...",
    "reason": "low_confidence",
    "expires_at": "..."
  }
}
```

Answering yes sends the token back, on its own. The parked parameters are the ones that
were described, so a caller cannot smuggle different figures in behind a token it already
holds. A token is bound to the user and the business that raised it, works once, and
expires after a few minutes.

A different kind of pause is `clarification_required`: the answer is not yes or no, it is
*which one* — two Marys, or a party who owes in both directions. Nothing is parked,
because the instruction was not specific enough to confirm.

A new name that needs confirming is rolled back before the question is asked, so a
question that is never answered leaves no half-finished customer behind.

**Rules enforced by the backend**

- There is no tool that is not on the published list
- A write that cannot be carried out is `rejected` with a reason a person can be told
- Asking a question never creates a record
- A confirmation cannot be reused, expired, spent on another tool, or spent on another
  business — including another of the same user's businesses

An interactive OpenAPI/Swagger schema arrives in phase B9.

---

## Testing

```bash
cd backend
pytest
```

Currently **312 tests**, running in about 17 seconds:

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
| **Ledger** | Money direction, payment consistency, overpayment, corrections |
| Ledger queries | Filters by type, status, method, source, date and party |
| **Debts** | Instalments, balances, overpayment, write-offs, aging buckets |
| Debt sync | Credit transactions opening debts, and payments settling them back |
| **Cash position** | Accrual against cash, and money counted exactly once |
| Summaries | Period boundaries, profit estimation, credit given, breakdowns |
| Float risk | Risk levels, horizons, overdue and undated obligations |
| Daily brief | Sentence wording, and facts kept distinct from estimates |
| **Agent registry** | The published tool list, and nothing else |
| Agent writes | Spoken names, voice source, the same validation as the REST API |
| Confirmation | Low confidence, unusual amounts, new names, single-use tokens |
| Clarification | Ambiguous names, and a party owing both ways |

Useful variations:

```bash
pytest -v                                   # verbose
pytest tests/test_businesses_isolation.py   # one module
pytest -k "isolation"                       # match by name
pytest --create-db                          # rebuild the test database
```

Tests run under `config/settings/test.py`, which uses a fast password hasher and reuses
the test database. Your development data is never touched.

Testing expands with each phase; AI extraction accuracy is measured during the voice
phases.

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
| `AGENT_CONFIDENCE_THRESHOLD` | `0.75` | Below this, a write waits for a yes |
| `AGENT_UNUSUAL_AMOUNT_FACTOR` | `5` | Multiple of a typical sale treated as possibly misheard |
| `AGENT_CONFIRMATION_TTL_SECONDS` | `300` | How long a pending confirmation stays answerable |

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
│   │   ├── catalog/           # Products and units
│   │   ├── ledger/            # Transactions
│   │   │   ├── models.py      # Transaction, types, statuses, sources
│   │   │   ├── services.py    # The only write path for money
│   │   │   ├── serializers.py
│   │   │   └── views.py
│   │   ├── debts/             # Receivables and payables
│   │   │   ├── models.py      # Debt, DebtPayment, aging buckets
│   │   │   ├── services.py    # Payments, write-offs, ledger sync
│   │   │   ├── serializers.py
│   │   │   └── views.py
│   │   ├── finance/           # Derived figures, no models of its own
│   │   │   ├── selectors.py   # The only place numbers are calculated
│   │   │   ├── periods.py     # "today", "week", "month" → date ranges
│   │   │   ├── brief.py       # Facts and estimates turned into sentences
│   │   │   ├── serializers.py
│   │   │   └── views.py
│   │   └── agent/             # Tool registry and confirmation, no LLM
│   │       ├── registry.py    # The fixed list of operations
│   │       ├── tools.py       # Thin wrappers over domain services
│   │       ├── resolvers.py   # Spoken names → records
│   │       ├── confirmation.py
│   │       ├── execution.py   # Validate → resolve → maybe ask → write
│   │       └── views.py
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
│   │   ├── test_agent_confirmation.py
│   │   ├── test_agent_isolation.py
│   │   ├── test_agent_reads.py
│   │   ├── test_agent_registry.py
│   │   ├── test_agent_writes.py
│   │   ├── test_catalog.py
│   │   ├── test_debts_crud.py
│   │   ├── test_debts_from_transactions.py
│   │   ├── test_debts_isolation.py
│   │   ├── test_debts_payments.py
│   │   ├── test_debts_queries.py
│   │   ├── test_finance_brief.py
│   │   ├── test_finance_cash_position.py
│   │   ├── test_finance_float_risk.py
│   │   ├── test_finance_isolation.py
│   │   ├── test_finance_summary.py
│   │   ├── test_health.py
│   │   ├── test_ledger_isolation.py
│   │   ├── test_ledger_queries.py
│   │   ├── test_ledger_relations.py
│   │   ├── test_ledger_transactions.py
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
| B5 | Financial ledger — transactions, methods, statuses, `source` | ✅ Complete |
| B6 | Debt management — receivables, payables, partial payments, aging | ✅ Complete |
| B7 | Financial intelligence — cash position, summaries, float risk | ✅ Complete |
| B8 | Agent tool contracts and confirmation model (no LLM yet) | ✅ Complete |
| B9 | OpenAPI docs, rate limiting, audit coverage, full regression suite | Next |

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
