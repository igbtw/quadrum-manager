# quadrum Architecture

This document describes the verified structure of quadrum based on the current source code. It is intended to help reviewers and contributors navigate the application quickly.

## Application Overview

quadrum is a single Django project (`config/`) with one primary application (`frontend/`). It is a demonstration Simple Management System that uses Django templates for rendering and SQLite for local development. Production deployment uses PostgreSQL (optional), Gunicorn, and WhiteNoise for static files.

## Django Settings (`config/`)

- `settings.py` uses environment variables (`DJANGO_DEBUG`, `DJANGO_SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`/`DB_*`) to switch between development and production behavior.
- Production mode (`DEBUG=False`) enforces `SECRET_KEY`, `ALLOWED_HOSTS`, and `CSRF_TRUSTED_ORIGINS` via `ValueError` checks.
- `STORAGES` configures WhiteNoise (`CompressedManifestStaticFilesStorage`) in production and standard Django static-file storage in development.
- `MIDDLEWARE` includes `whitenoise.middleware.WhiteNoiseMiddleware` (required for production static-file serving).

## Request Flow

A simplified flow for a protected view (e.g., `/sales/new/`):

```
URL (frontend/urls.py) -> View (frontend/views.py) -> Model query/update -> Template render -> HTTP response
```

- `config/urls.py` routes `/` to `frontend.urls` and `/admin/` to Django admin.
- `frontend/urls.py` defines routes for the dashboard, sales, products, inventory, people, finance, reports, documentation (index at `/documentation/` and topic pages at `/documentation/<slug:topic_slug>/`), login/register/logout, onboarding state endpoints (`/onboarding/complete/`, `/onboarding/skip/`, `/onboarding/step/`, `/onboarding/restart/`), and API endpoints (`/api/pos/calculate/`, `/api/pos/finalize/`, `/api/search/`; legacy aliases `/api/pdv/calcular/`, `/api/pdv/finalizar/`).
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
- `User` -> `OnboardingProgress` (one-to-one, cascade delete)

Key design decisions from the code:

- Idempotency keys (`Sale.idempotency_key`) prevent duplicate checkout requests. The fingerprint (`request_fingerprint`) verifies that repeated requests use identical data.
- `SaleItem.subtotal` is computed automatically (`quantity * unit_price`).
- `AccountReceivable.remaining_balance` and status updates are handled by `register_payment()` within a transaction (`select_for_update`).
- Stock adjustments (`adjust_stock`) create `StockMovement` records; sales finalization (`finalize_sale`) reduces `Product.stock_quantity` and creates movement records.
- `OnboardingProgress` stores first-run guide state (`current_step`, `completed_at`/`skipped_at`) per user. Rows are created when a user registers or replays the guide; users without a row (including accounts created before the feature) are never shown the onboarding dialog. `current_step` (0-based) tracks the guide's resume position across page navigations and sessions.

## Views (`frontend/views.py`)

Verified view categories:

- Public: `health_check`, `login_view`, `register_view`, `logout_view`
- Protected (`@login_required`): `dashboard`, `sales_list`, `point_of_sale`, `product_list`, `inventory`, `people`, `finance`, `reports`, `documentation`
- Protected state changes (`@login_required` + `@require_http_methods(["POST"])`): `onboarding_complete`, `onboarding_skip`, `onboarding_step` (JSON, validates `0..ONBOARDING_TOTAL_STEPS-1`, returns 400/409 on invalid or inactive state), `onboarding_restart` (resets `current_step` to 0; redirect only through `_safe_next_url()`)
- API (`@require_http_methods(["POST"])` + `@login_required`): `api_pos_calculate` (cart total), `api_pos_finalize` (atomic sale creation with idempotency)

The dashboard aggregates counts and sums from `Sale`, `AccountReceivable`, and `Product`.

## Static Files and Templates

- Global static assets: `static/css/`, `static/js/`, `static/favicon.svg`
- Application templates: `frontend/templates/frontend/` (namespaced; verified by settings `APP_DIRS = True`)
- Custom error templates: `frontend/templates/400.html`, `frontend/templates/403.html`, `frontend/templates/404.html`, `frontend/templates/500.html`

WhiteNoise handles static-file compression and manifest in production (`STORAGES`).

## Authentication and Authorization

- Django built-in `User` model.
- `@login_required` protects operational pages (dashboard, sales, products, inventory, people, finance, reports) and the POS APIs.
- **Public self-service registration is enabled** (`/register/`, `frontend:register`). Any successfully registered account can access all operational pages and data currently protected only by `@login_required`, including Dashboard, Sales, Products, Inventory, People, Finance, and Reports. This is an approved product policy, not accidental privilege escalation.
- New accounts are always ordinary authenticated users: registration never grants Django staff or superuser privileges, and the form exposes no privileged fields. Django admin (`/admin/`) and any explicitly privileged operations remain protected by their own authorization rules.
- There is no staff-approval, invitation, or email-verification step. Do not infer one from this document.
- `CSRF_TRUSTED_ORIGINS` and cookie security (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`) are enabled when `DEBUG=False`.
- No custom roles or groups are implemented; authorization relies on authentication presence.

## Database Configuration

- Default: SQLite (`db.sqlite3` at project root, excluded by `.gitignore`).
- Production: configured via `DATABASE_URL` or `DB_ENGINE` + `DB_*` variables. PostgreSQL is the intended production backend.
- Migrations exist for `frontend` (verified: 8 migrations in `frontend/migrations/`).

## Important Design Notes (Verified)

- Django view names, URL names, and canonical POS API paths (`/api/pos/calculate/`, `/api/pos/finalize/`) use English. The legacy POS paths (`/api/pdv/calcular/`, `/api/pdv/finalizar/`) remain registered as aliases for compatibility.

- `.env` is **not** loaded automatically by Django or the application. Variables must be exported in the environment or provided by the deployment mechanism (`DEPLOYMENT.md` covers `EnvironmentFile` for systemd).
- The application uses a single app (`frontend`) for business logic, rather than splitting into multiple Django apps.
- The onboarding dialog is gated by the `frontend.context_processors.onboarding` context processor (`onboarding_pending` + `onboarding_step`): it is only rendered for authenticated users with a pending `OnboardingProgress` row. `static/js/main.js` (`initOnboarding`) enhances it into a stepper that persists the current step (CSRF-protected `fetch` to `onboarding_step`, awaited before navigation), dims the page with a spotlight cutout over the matching sidebar destination, and blocks the global search/sidebar shortcuts while active; without JavaScript all steps and the skip/finish forms remain usable. The repository's Markdown documentation is **not** served by the application; the in-app portal is an operator-facing summary.

- The documentation portal is registry-driven. `DOC_TOPICS` in `frontend/search.py` is the single source of truth: it defines each topic's slug, title, description, keywords, group (end-user help vs. developer reference), icon, and **fixed template path**. `frontend:documentation` renders the index (cards, search field, guide replay) from the registry; `frontend:documentation_topic` validates the `<slug:topic_slug>` against the registry and renders `topic['template']` (never a user-derived template name), raising `Http404` for unknown slugs. The `frontend.context_processors.documentation` processor exposes `doc_topics` to every template so `base.html` renders the palette's `#searchDocData` island from the same registry. The index's search field filters the rendered topic cards client-side by title, description, and keywords (`initDocsPage` in `static/js/main.js`).

- Global search is split between the palette (`static/js/main.js`, `initSearchPalette`) and the server (`frontend:api_search`). The palette keeps the raw query, renders static page/documentation matches instantly from the `#searchPageData` and `#searchDocData` islands in `base.html`, and debounces a `fetch` to the server for products, people, and sales. With an empty field it renders per-tab browse groups (All, Pages, Docs, Products, People, Sales) instead of query results; switching tabs mid-request shows a "Searching…" notice rather than a premature empty state for server-owned categories. Query parsing is authoritative in `frontend/search.py` (`SEARCH_PREFIXES`, `parse_search_query`): recognized prefixes (`page:`, `doc:`, `product:`, `person:`, `sale:`) are case-insensitive and scope the search to one group; an empty prefixed term returns a per-group prompt; unknown prefixes remain ordinary text. Page results use the app routes, `doc:` results use `frontend:documentation_topic` URLs, and server-backed results deep-link into the corresponding list pre-filtered: `person:` → `/people/?q=<name>`, `product:` → `/products/?q=<code-or-name>`, `sale:` → `/sales/?q=<code>`. `PAGE_REGISTRY` and `DOC_TOPICS` mirror the template islands, and `frontend/tests/test_search.py` asserts the two stay in sync.

- List pages share small helpers in `frontend/listsearch.py`: `normalize_q` (whitespace collapse plus a 100-character bound), `parse_iso_date`, `build_querystring` (bookmark-safe links that always drop the page parameter, keep only allowlisted keys per table, and can override single values for sort toggles), `sort_state`/`sort_headers` (per-page sort allowlists with deterministic `id` tie-breakers and `aria-sort`/arrow metadata), and `paginate` (configurable page parameter so Finance's two tables use `rpage` and `ppage` independently). Each view still owns its queryset and filter semantics — the shared pieces only guarantee identical edge-case behavior (invalid filters, dates, sorts, and pages degrade to safe defaults). Filter state travels exclusively in GET parameters, so any filtered view is shareable. The records-per-page preference is session-backed: `frontend:preferences_per_page` (POST-only, login required, allowlisted to 10/20/40) stores `request.session['per_page']`, and `frontend.context_processors.preferences` exposes both the effective value and the option list so the Preferences dialog always reflects the size list views actually use.

## Unverified / Planned

- No evidence of external integrations (email sending is configured but not verified as operational).
- No custom user roles beyond Django's default `User`.
- No automated backup or restore mechanism inside the application code (backups are documented as external procedures in `DEPLOYMENT.md`).
