# quadrum

A Django-based **Simple Management System** for product inventory, point-of-sale (POS) sales, accounts receivable, and basic reporting. Built with Django templates and vanilla CSS/JavaScript.

> **Note:** Django view names, URL names, and POS API paths are standardized in English. The legacy POS API paths remain available as aliases for compatibility with existing integrations. Historical database migrations remain unchanged.

## Current Status

- **Implemented:** Product and inventory management (categories, products, stock adjustments); point-of-sale with idempotency keys; sales finalization with automatic stock reduction; accounts receivable and payments; basic dashboard, reports, and health endpoint; authentication and access control (`@login_required`) with dedicated login/registration pages and public self-service registration (`/register/`).
- **In progress / planned:** Additional integrations, multi-tenant support, and production hardening are not present in the codebase.
- **Not implemented:** External APIs, automated backups as application features, mobile apps, or advanced analytics.

## Technology Stack

- **Framework:** Django 5.2+ (`>=5.2,<5.3`)
- **Language:** Python 3.11+ (tested on 3.14.7)
- **WSGI server:** Gunicorn 21+
- **Static files:** WhiteNoise 6.8+ (required for production; configured in `STORAGES` and middleware)
- **Database:** SQLite (development); PostgreSQL 14+ (production, optional)
- **Dependencies:** See [requirements.txt](requirements.txt) (includes `whitenoise`, `gunicorn`, `python-dotenv`, `psycopg[binary]`)
- **Frontend:** Django templates + vanilla CSS/JS (no build step)
- **License:** 0BSD (see [LICENSE](LICENSE))

## Project Structure

```
config/          Django settings, URLs, WSGI/ASGI
frontend/        Main app: models, views, forms, templates, tests
static/          Global static assets (CSS, JS, favicon)
docs/            Architecture documentation and the documentation index
manage.py        Django CLI
```

## Documentation

- [Documentation index](docs/index.md) — starting point for all quadrum documentation
- [Architecture](docs/architecture.md) — project layout, request flow, and data model details
- [Contributing](CONTRIBUTING.md) — development setup, checks, and guidelines
- [Deployment](DEPLOYMENT.md) — the canonical deployment and operations guide

Signed-in users also have an in-app **Documentation** portal: the `/documentation/` index page lists every topic as a card with its own description, a topic search field, and links to dedicated pages (`/documentation/<topic>/`) for getting started, dashboard, products and inventory, sales and POS, people, finance, data models, API reference, preferences and troubleshooting, and search syntax. Topic pages have breadcrumbs, a topic sidebar, and previous/next navigation; the getting started guide can be replayed from the index. The repository files above remain the internal source of truth and are not served by the application.

## Local Development

### Prerequisites

- Python 3.11+
- `pip` and `virtualenv` (recommended)

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # Adjust if needed
python manage.py migrate
python manage.py runserver
```

Access the app at `http://localhost:8000`.

> **Important:** Django does **not** load `.env` automatically. The `.env` file is convenient for manual setup, but variables must be exported or provided by the hosting environment (e.g., `EnvironmentFile` for systemd) in production. See `.env.example` and `DEPLOYMENT.md`.

## Testing

Run the full test suite (487 verified tests):

```bash
python manage.py test
```

Other useful checks:

```bash
python manage.py check
python manage.py check --deploy   # Review production-style warnings
python manage.py collectstatic --noinput --dry-run
```

## Demo Data (Development Only)

For presentations and manual QA, two management commands create and remove a
realistic, clearly labeled dataset:

```bash
python manage.py seed_demo_data            # --seed N for reproducible data (default 42)
python manage.py clear_demo_data
```

- Both commands only run when `ALLOW_DEMO_DATA_COMMANDS` is enabled (defaults
  to `DEBUG`) and refuse to run otherwise. **Never enable them in production.**
- `seed_demo_data` creates 6 `demo_*` accounts (shared password `Demo@1234`,
  e.g. `demo_ana.souza`), 8 categories, 42 products, 24 people, 80 sales
  (72 completed, 4 pending, 4 cancelled), 10 receivables with coherent payment
  history, and stock movements whose running balances exactly reproduce each
  product's final stock.
- Every created primary key is recorded in a JSON manifest at
  `DEMO_DATA_MANIFEST_PATH` (`demo_data_manifest.json`, gitignored) **before**
  the database transaction commits, so a committed dataset is always
  identifiable; if seeding fails, the transaction is rolled back and the
  manifest is removed.
- `clear_demo_data` deletes exactly those rows (including sessions created by
  demo users after seeding) and aborts without deleting anything when
  untracked records reference the dataset. Non-demo accounts such as `root`
  and all unrelated records are never touched.

## Configuration

Key environment variables (see `.env.example`):

| Variable | Purpose | Required in production? |
|----------|---------|------------------------|
| `DJANGO_DEBUG` | Development/debug mode (`True`/`False`) | Must be `False` |
| `DJANGO_SECRET_KEY` | Cryptographic secret | **Yes** (must not use the default dev value) |
| `ALLOWED_HOSTS` | Allowed hostnames (CSV) | **Yes** |
| `CSRF_TRUSTED_ORIGINS` | HTTPS origins for CSRF (CSV) | **Yes** |
| `DATABASE_URL` | PostgreSQL connection string | Only if using PostgreSQL |
| `DB_ENGINE` / `DB_*` | Alternative database settings | Only when not using `DATABASE_URL` |

Secret-bearing files (`.env`, `.env.*`) are excluded by `.gitignore`.

## Deployment

Deployment instructions, reverse proxy configuration (nginx/Apache), HTTPS setup, service manager files, and backup procedures are documented in `DEPLOYMENT.md`. The deployment guide covers conditional steps for systemd and OpenRC, database creation, static-file collection, and post-deployment verification.

## Features (Verified)

- Product categories and inventory with minimum-stock alerts
- Point-of-sale (POS) with item calculation, idempotency keys, and atomic finalization
- Sales history and stock adjustments with audit trails (`StockMovement`)
- Accounts receivable (`AccountReceivable`) and payment registration (`Payment`)
- Payment safety and financial integrity: eligibility is recomputed from the ledger (cancelled and fully settled accounts reject new payments, over-balance amounts are refused) instead of trusting the displayed status, so a stale `PAID` row with a real balance stays payable; monetary math is exact two-decimal `Decimal` with SQLite float-derived sums normalized; every payment carries a server-generated idempotency key (a replay resolves to the original payment, while reusing a key with different parameters is rejected); ORM/admin saves are guarded against overpayment, settled-account inserts and reassignment abuse, and the database enforces `original_amount >= 0.01`; a read-only `manage.py audit_financials` command reports stale statuses, overpayments, cancelled-with-payments, sale/receivable mismatches and duplicate keys without modifying data.
- Operational analytics on Reports (server-rendered, no mock data): global local-timezone filters (Today, Yesterday, Last 7/30 days, This month, and a custom range capped at 366 days) plus status, payment-method, category, and responsible-user filters that stay active across every KPI, chart, ranking, and the transaction table; invalid ranges or unknown choices surface as form validation errors with a safe fallback period. It includes a completed-sales KPI strip with equal-length preceding-period comparisons (neutral "no activity", no division by zero), zero-filled revenue/volume trends with a previous-period overlay and compatible daily or 7-day buckets, payment-method mix, status breakdown, product rankings by units and by revenue with category breakdowns and item-revenue share, an estimated margin card based on current recorded product costs (items without recorded cost are disclosed and excluded; never labeled profit), receivables analytics (payments received in period, outstanding and overdue balances, aging buckets), a paginated and sortable transaction table, and a CSV export that reuses the same validated filters. Sales revenue, payments received, and outstanding receivables are reported separately, and category filters are applied as sale-level subqueries so joined sale items cannot double count transaction totals.
- Server-side list search on every listing page (Sales, Products, Inventory, People, Finance): search boxes, dropdown filters, and date ranges submit as GET forms (`?q=...&status=...`), so filtered views are shareable and bookmarkable. Every list shows a live result count, honest contextual empty states, and pagination (default 20 rows, adjustable from 10 to 40 under Preferences). Products and People keep Active as the default state with explicit Inactive/All options; the Inventory list includes inactive products by default. Sales and receivables tables are sortable with `aria-sort` headers; Finance hosts two independently paginated tables (receivables `rpage`, payments `ppage`).
- Searchable Preferences palette (theme, density, corner style, sidebar, motion, text size, accent
  color, high contrast, destructive-action confirmations). Visual settings live in
  `localStorage` (`quadrum.preferences.v1`) and are local to the current browser;
  they never sync across devices. Square corners are the default; Rounded
  restores the classic radii. "Records per page" is deliberately server-backed:
  it is stored in the signed-in user's session via `/preferences/per-page/`
  so pagination stays consistent on every list page.
- Health endpoint (`/health/`) returning `{"status":"ok","service":"quadrum"}`
- First-run onboarding guide for newly registered accounts (server-side `OnboardingProgress` state; skip, complete, and replay supported; the current step persists across page navigation)
- Global search palette (`Ctrl+K`): browse tabs (All, Pages, Docs, Products, People, Sales) when the field is empty, live search while typing, and advanced prefixes `page:`, `doc:`, `product:`, `person:`, `sale:` that scope the query to one resource type. Results always link to real destinations — documentation results open the dedicated topic page, people results open the People listing pre-filtered by the matched name (`/people/?q=...`), and product/sale results deep-link to their lists pre-filtered by code or name (`/products/?q=...`, `/sales/?q=...`). The syntax is documented in the Documentation portal's "Search and Advanced Queries" topic.
- In-app Documentation portal for signed-in users: an index page at `/documentation/` with topic cards and search, plus one dedicated page per topic
- User authentication (`@login_required` on protected views); responsible-based data isolation: sales, receivables and payments are visible only to the user recorded as the sale's responsible, while superusers and users explicitly granted the `frontend.view_all_responsible_data` permission (directly or via a group) see every record. Records with no ownership path (a receivable with no sale) are global-only. Shared master data (products, categories, people) stays visible to every signed-in user.
- Record management for People and Products: users with the `frontend.manage_master_data` permission (or superusers) can edit records through a modal form and delete them through a confirmation dialog. Deletes are POST-only with CSRF protection and refuse records referenced by history — people with sales or receivables, products with sale items or stock movements — explaining the references and pointing to deactivation (`Active` unchecked in the edit form) as the archive path. Records without references delete cleanly. Failed validations re-render the form with the submitted values and error messages.
- Public self-service registration (`/register/`) with Django password validation and CSRF protection. **Product policy:** any successfully registered account can access the operational pages (Dashboard, Sales, Products, Inventory, People, Finance, Reports), but business records are scoped to what the account is responsible for as described above. Registration never grants Django staff or superuser privileges — ordinary application access and administrative privileges are distinct.

## License

quadrum is licensed under the 0BSD (BSD Zero Clause) License. See [LICENSE](LICENSE) for the full text.

Third-party dependencies (Django, WhiteNoise, Gunicorn, etc.) remain subject to their respective licenses.
