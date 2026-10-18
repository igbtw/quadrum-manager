# quadrum Architecture

This document describes the verified structure of quadrum based on the current source code. It is intended to help reviewers and contributors navigate the application quickly.

## Application Overview

quadrum is a single Django project (`config/`) with one primary application (`frontend/`). It is designed as a demonstration of school cafeteria management, using Django templates for rendering and SQLite for local development. Production deployment uses PostgreSQL (optional), Gunicorn, and WhiteNoise for static files.

## Django Settings (`config/`)

- `settings.py` uses environment variables (`DJANGO_DEBUG`, `DJANGO_SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`/`DB_*`) to switch between development and production behavior.
- Production mode (`DEBUG=False`) enforces `SECRET_KEY`, `ALLOWED_HOSTS`, and `CSRF_TRUSTED_ORIGINS` via `ValueError` checks.
- `STORAGES` configures WhiteNoise (`CompressedManifestStaticFilesStorage`) in production and standard Django static-file storage in development.
- `MIDDLEWARE` includes `whitenoise.middleware.WhiteNoiseMiddleware` (required for production static-file serving).

## Request Flow

A simplified flow for a protected view (e.g., `/sales/nova/`):

```
URL (frontend/urls.py) -> View (frontend/views.py) -> Model query/update -> Template render -> HTTP response
```

- `config/urls.py` routes `/` to `frontend.urls` and `/admin/` to Django admin.
- `frontend/urls.py` defines routes for the dashboard, sales, products, inventory, people, finance, reports, login/logout, and two API endpoints (`api_pdv_calcular/`, `api_pdv_finalizar/`).
- Protected views use `@login_required`. The health endpoint (`/health/`) is public.

## Data Model (`frontend/models.py`)

Verified entities and relationships:

- `Category` -> `Product` (one-to-many, `PROTECT` on delete)
- `Person` (student/staff/visitor) -> `Sale` (optional customer, `SET_NULL`)
- `Sale` -> `SaleItem` (cascade delete), with `idempotency_key` (unique, indexed) and `request_fingerprint`
- `Product` -> `SaleItem` (`PROTECT` on delete)
- `Sale` -> `AccountReceivable` (optional, `SET_NULL`)
- `AccountReceivable` -> `Payment` (`PROTECT` on delete)
- `Product` -> `StockMovement` (`PROTECT` on delete)

Key design decisions from the code:

- Idempotency keys (`Sale.idempotency_key`) prevent duplicate checkout requests. The fingerprint (`request_fingerprint`) verifies that repeated requests use identical data.
- `SaleItem.subtotal` is computed automatically (`quantity * unit_price`).
- `AccountReceivable.remaining_balance` and status updates are handled by `register_payment()` within a transaction (`select_for_update`).
- Stock adjustments (`adjust_stock`) create `StockMovement` records; sales finalization (`finalize_sale`) reduces `Product.stock_quantity` and creates movement records.

## Views (`frontend/views.py`)

Verified view categories:

- Public: `health_check`, `login_view`, `logout_view`
- Protected (`@login_required`): `dashboard`, `sales_list`, `pdv`, `products`, `inventory`, `people`, `finance`, `reports`
- API (`@require_http_methods(["POST"])` + `@login_required`): `api_pdv_calcular` (cart total), `api_pdv_finalizar` (atomic sale creation with idempotency)

The dashboard aggregates counts and sums from `Sale`, `AccountReceivable`, and `Product`.

## Static Files and Templates

- Global static assets: `static/css/`, `static/js/`, `static/favicon.svg`
- App-level static assets: `frontend/static/`
- Templates: `frontend/templates/frontend/` (verified by settings `APP_DIRS = True`)

WhiteNoise handles static-file compression and manifest in production (`STORAGES`).

## Authentication and Authorization

- Django built-in `User` model.
- `@login_required` protects operational pages.
- `CSRF_TRUSTED_ORIGINS` and cookie security (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`) are enabled when `DEBUG=False`.
- No custom roles or groups are implemented; authorization relies on authentication presence.

## Database Configuration

- Default: SQLite (`db.sqlite3` at project root, excluded by `.gitignore`).
- Production: configured via `DATABASE_URL` or `DB_ENGINE` + `DB_*` variables. PostgreSQL is the intended production backend.
- Migrations exist for `frontend` (verified: 4 migrations in `frontend/migrations/`).

## Important Design Notes (Verified)

- URL route names (`frontend/urls.py`) use English paths (`sales/`, `inventory/`, etc.) but keep original name identifiers for compatibility.

- `.env` is **not** loaded automatically by Django or the application. Variables must be exported in the environment or provided by the deployment mechanism (`DEPLOYMENT.md` covers `EnvironmentFile` for systemd).
- The application uses a single app (`frontend`) for business logic, rather than splitting into multiple Django apps.

## Unverified / Planned

- No evidence of external integrations (email sending is configured but not verified as operational).
- No custom user roles beyond Django's default `User`.
- No automated backup or restore mechanism inside the application code (backups are documented as external procedures in `DEPLOYMENT.md`).
