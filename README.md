# quadrum

A Django-based web application for managing a school cafeteria. It provides product inventory, point-of-sale (PDV) sales, accounts receivable, and basic reporting using Django templates and vanilla CSS/JavaScript.

> **Note:** Django view names and URL names have been standardized in English. Historical database migrations and existing HTTP URL paths remain unchanged — including the two POS API paths — for compatibility with existing links.

## Current Status

- **Implemented:** Product and inventory management (categories, products, stock adjustments); point-of-sale with idempotency keys; sales finalization with automatic stock reduction; accounts receivable and payments; basic dashboard, reports, and health endpoint; authentication and access control (`@login_required`).
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

Run the full test suite (56 verified tests):

```bash
python manage.py test
```

Other useful checks:

```bash
python manage.py check
python manage.py check --deploy   # Review production-style warnings
python manage.py collectstatic --noinput --dry-run
```

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
- Point-of-sale (PDV) with item calculation, idempotency keys, and atomic finalization
- Sales history and stock adjustments with audit trails (`StockMovement`)
- Accounts receivable (`AccountReceivable`) and payment registration (`Payment`)
- Basic dashboard statistics and reports
- Health endpoint (`/health/`) returning `{"status":"ok","service":"quadrum"}`
- User authentication (`@login_required` on protected views); no custom user roles implemented

## License

quadrum is licensed under the 0BSD (BSD Zero Clause) License. See [LICENSE](LICENSE) for the full text.

Third-party dependencies (Django, WhiteNoise, Gunicorn, etc.) remain subject to their respective licenses.
