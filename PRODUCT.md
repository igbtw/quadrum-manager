# CantinaOS

## Product

- **Name:** CantinaOS
- **Purpose:** Sistema de gerenciamento de cantina escolar (school cafeteria management system)
- **What it makes possible:** Manage school cafeteria operations — likely menu planning, orders, inventory, student access — via Django web app
- **Positioning:** Local-school, Django-based; no evidence of multi-tenant or SaaS positioning
- **Language / locale:** Portuguese (README, copy); default likely pt-BR

## Users & Jobs

- **Primary user (inferred):** School cafeteria staff / administrators; possibly students or parents for ordering/viewing
- **Situation:** School environment, daily operations
- **Job:** Track cafeteria orders, menu, inventory, or student payments
- **Open:** Exact role split (admin vs. student vs. parent) not confirmed in repo; model names (`frontend/models.py`) should be inspected for confirmation

## Capabilities & Constraints

- Web (Django 4/5 pattern, `manage.py`, `config/settings.py`)
- SQLite (`db.sqlite3` present)
- Portuguese-language UI and docs
- `frontend/` app holds models/views/admin/mock_data; templates in `templates/`; static in `static/`
- No evidence of REST API / DRF; likely server-rendered templates
- No design system artifact (`DESIGN.md`, tokens) present — visual world unrecorded

## Evidence

- `README.md`: installation (Python 3.11+, venv, pip), .env.example, basic project description
- `frontend/models.py`, `frontend/admin.py`, `frontend/views.py`, `frontend/urls.py`: core app
- `db.sqlite3`: developed locally
- `frontend/mock_data.py`: suggests demo / seed data capability

## Platform

- **Web** (not native iOS/Android; no mobile wrapper evidence)
- Entry: `python manage.py runserver` (inferred standard Django)
- Responsive status unknown; to verify

## Stack

- Python 3.11+, Django, SQLite (dev), pip/venv
- No JS framework evidence (check `frontend/static/` if needed)
- No Docker evidence; deploy target unknown
- Stack choice not delegated; kept as-is from repo

## Voice / Brand

- Functional / institutional (school administration tool)
- No logo, color, or typography commitment recorded
- Copy is direct/Portuguese; no marketing tone

## Open Decisions

- Primary user roles and exact workflows (needs interview or model inspection)
- Visual design world (new-work / document needed)
- Accessibility targets (no audit performed)
- Deployment / production DB (env-configured via `.env`)
- Whether `frontend/` is the only app or more exist

## Replaced / Superseded

- None; this is first PRODUCT.md for project.
