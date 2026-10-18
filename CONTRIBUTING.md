# Contributing to quadrum

quadrum is a demonstration Django application for school cafeteria management. Contributions should be small, reviewable, and focused on fixing verified issues or adding clearly needed functionality.

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # Template only; does NOT load automatically
```

Environment variables must be exported or set explicitly. Example for local development:

```bash
export DJANGO_DEBUG=True
export DJANGO_SECRET_KEY="django-insecure-dev-key-change-in-production"
export ALLOWED_HOSTS="localhost,127.0.0.1,0.0.0.0"
python manage.py migrate
python manage.py test
python manage.py runserver
```

> Django does **not** load `.env` automatically. Installing `python-dotenv` does not change this behavior. Variables must be exported in the shell or provided by the hosting mechanism (e.g., `EnvironmentFile` for systemd in production). See `DEPLOYMENT.md`.

## Running Checks

Before proposing changes:

```bash
python manage.py check
python manage.py test
python manage.py collectstatic --noinput --dry-run
```

The clean-environment installation (`pip install -r requirements.txt`) has been verified to include all required dependencies (`Django`, `gunicorn`, `whitenoise`, `python-dotenv`, `psycopg[binary]`).

## Guidelines

- Make small, targeted changes with clear descriptions.
- Do not invent new user roles, integrations, or major architecture changes unless verified against the project design.
- Do not commit secrets, `.env` files, real school/student data, or database files (`db.sqlite3`, `media/`, `staticfiles/`).
- Verify commands and feature claims against the actual repository before documenting them.
- Preserve the 0BSD license and existing documentation structure (`DEPLOYMENT.md`, `README.md`).

## Reporting Issues

Report bugs or propose changes by describing the actual behavior observed, the expected behavior, and the steps to reproduce. Include relevant environment details (Python version, Django version, and whether the issue appears in both SQLite and PostgreSQL if applicable).
