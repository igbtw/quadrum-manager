# quadrum Deployment Guide

This document describes how to deploy quadrum to a production server.
It separates **application-level requirements** (what the app needs) from
**OS-specific instructions** (how to install packages on your Linux
distribution). OS-specific commands are marked as conditional.

> **Scope**: This is a demonstration deployment with fictitious data. The steps here
> are suitable for a single-server deployment behind a reverse proxy with HTTPS.

---

## 1. Runtime Requirements

| Requirement | Details |
|---|---|
| **Python** | 3.12, 3.13, or 3.14 (developed on 3.14) |
| **Django** | 5.2.x |
| **Database** | PostgreSQL 14+ (recommended for production); SQLite 3.31+ supported by Django 5.2 but not interchangeable for all production workloads |
| **WSGI server** | Gunicorn 21+ |
| **Static file middleware** | WhiteNoise 6.8+ (declared in `requirements.txt`; configured in `STORAGES` and middleware) |
| **Reverse proxy** | nginx or Apache (recommended) |
| **OS** | Any modern Linux distribution (Alpine, AlmaLinux, Ubuntu, Debian, etc.) |

---

## 2. Required Environment Variables

Copy `.env.example` to `.env` and set the following in production:

### Required (no defaults)

> ⚠️ **Production requires `DJANGO_DEBUG=False`.** When `DJANGO_DEBUG` is missing or set to `True`, `DEBUG` defaults to `True` (development mode) and production checks (`SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`) are NOT enforced. A server started with `DEBUG=True` or without `DJANGO_DEBUG` set will not fail silently — it will start in development mode, which is unsafe for production. Always set `DJANGO_DEBUG=False` explicitly in production.

| Variable | Example | Description |
|---|---|---|
| `DJANGO_DEBUG` | `False` | Must be `False` in production. Default is `True`; the settings file validates production values only when `DEBUG=False`. |
| `DJANGO_SECRET_KEY` | (see §3) | A cryptographically random 50+ character key. **Never reuse the dev key (`django-insecure-dev-key-change-in-production`).** |
| `ALLOWED_HOSTS` | `yourdomain.com,www.yourdomain.com` | Comma-separated list of host/domain names. Empty in production raises `ValueError`. |
| `CSRF_TRUSTED_ORIGINS` | `https://yourdomain.com,https://www.yourdomain.com` | Origins sending CSRF-protected POST requests. Must include scheme. Empty in production raises `ValueError`. |
| `DATABASE_URL` | `postgres://user:pass@localhost:5432/quadrum` | PostgreSQL connection string. When set, `DB_*` variables are not required. |

### Optional (production services)

| Variable | Default | Description |
|---|---|---|
| `DB_ENGINE` | `django.db.backends.sqlite3` | Use `django.db.backends.postgresql` if not using `DATABASE_URL`. |
| `DB_NAME` | — | PostgreSQL database name (required if `DB_ENGINE=postgresql`). |
| `DB_USER` | — | PostgreSQL user (required if `DB_ENGINE=postgresql`). |
| `DB_PASSWORD` | — | PostgreSQL password. |
| `DB_HOST` | `localhost` | PostgreSQL host. |
| `DB_PORT` | `5432` | PostgreSQL port. |
| `EMAIL_HOST` | `localhost` | SMTP server for email. |
| `EMAIL_PORT` | `587` | SMTP port. |
| `EMAIL_USE_TLS` | `True` | Use TLS for SMTP. |
| `EMAIL_HOST_USER` | — | SMTP username. |
| `EMAIL_HOST_PASSWORD` | — | SMTP password. |
| `DEFAULT_FROM_EMAIL` | `noreply@quadrum.local` | Default sender for outgoing email. |

> ⚠️ **Django does not load `.env` automatically.** The `python-dotenv` package is included in `requirements.txt`, but you must explicitly load it (e.g., via `python-dotenv` in Python or by exporting variables before starting Gunicorn). The `.env` file is for convenience during manual setup; production services should either use `EnvironmentFile` (systemd) or export variables explicitly. It is in `.gitignore`.

---

## 3. Creating the Production Secret Key

Use Python's `secrets` module or Django's built-in generator:

```bash
# Option A: Python (use any Python 3 interpreter)
python3 -c "import secrets; print(secrets.token_urlsafe(50))"

# Option B: Django (after creating the virtual environment)
.venv/bin/python manage.py shell -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the output to `DJANGO_SECRET_KEY` in your `.env` file on the server.

---

## 4. PostgreSQL Configuration

### Creating the Database (conditional — adapt to your OS)

```bash
# Create a dedicated user and database (PostgreSQL default setup)
sudo -u postgres createuser quadrum -P
sudo -u postgres createdb -O quadrum quadrum
```

### Network Restrictions

Edit PostgreSQL configuration to restrict remote access:

```bash
# PostgreSQL config file location varies by OS — typically:
# Ubuntu/Debian: /etc/postgresql/<version>/main/pg_hba.conf
# AlmaLinux/RHEL: /var/lib/pgsql/<version>/data/pg_hba.conf
# Alpine: /var/lib/postgresql/data/pg_hba.conf

# In pg_hba.conf, restrict access:
# TYPE  DATABASE  USER      ADDRESS      METHOD
local    all       all                   peer
host    quadrum  quadrum  127.0.0.1/32  md5
host    all        all      0.0.0.0/0        reject  # deny all other hosts

# In postgresql.conf:
listen_addresses = 'localhost'  # Only listen on loopback
```

Restart PostgreSQL after changes:
```bash
# Conditional (adapt to your OS):
# Ubuntu/Debian: sudo systemctl restart postgresql
# AlmaLinux/RHEL: sudo systemctl restart postgresql
# Alpine (OpenRC): sudo rc-service postgresql restart
```

---

## 5. Installing Dependencies

### Isolate the Python Environment

```bash
# Create a dedicated system user (conditional)
# sudo useradd -r -m -d /opt/quadrum quadrum

# Switch to the application directory
cd /opt/quadrum  # or wherever you deploy

# Create a virtual environment (use the system Python interpreter)
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies (includes Django, psycopg[binary], gunicorn, python-dotenv, and WhiteNoise)
pip install -r requirements.txt

# Confirm WhiteNoise middleware and STORAGES are configured in config/settings.py
```

---

## 6. Running Django Checks and Tests

Before starting the server:

```bash
# Activate the virtual environment
source .venv/bin/activate

# Run system checks
python manage.py check

# Run production checks (with production env vars set)
python manage.py check --deploy
```

Run the test suite (in a separate environment, not production):

```bash
source .venv/bin/activate
python manage.py test frontend.tests
```

---

## 7. Applying Migrations

> ⚠️ **Back up your database before applying migrations in production.**

```bash
source .venv/bin/activate

# Review pending migrations
python manage.py showmigrations

# Apply migrations
python manage.py migrate --noinput
```

> **Important**: Do not run production migrations against the local
> development database. Always use the production database URL.

---

## 8. Collecting Static Files

```bash
source .venv/bin/activate

# Collect static files to STATIC_ROOT
python manage.py collectstatic --noinput --clear
```

After this, static files are in `<BASE_DIR>/staticfiles/`.
WhiteNoise will serve these directly from the staticfiles directory.

---

## 9. Running the WSGI Server (Gunicorn)

```bash
source .venv/bin/activate

# Basic command (variables must be exported or passed explicitly; Django does not auto-load .env)
export DJANGO_DEBUG=False
export DJANGO_SECRET_KEY="your-secret-key-here"
export ALLOWED_HOSTS="yourdomain.com"
export CSRF_TRUSTED_ORIGINS="https://yourdomain.com"
export DATABASE_URL="postgres://user:pass@localhost:5432/quadrum"
gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3

# Alternative: load from .env file using python-dotenv in Python, or export variables manually
# Note: Using a systemd service with EnvironmentFile=/opt/quadrum/.env is preferred for production.
```

> **Workers**: Use `$(nproc)` or `2 * $(nproc) + 1` as a starting point.
> **Bind**: Use `127.0.0.1:8000` (not `0.0.0.0`) and let the reverse proxy
> handle public-facing traffic.

---

## 10. Reverse Proxy: nginx or Apache

This project supports nginx and Apache. Configure based on your OS.

### nginx Configuration (conditional)

```nginx
# /etc/nginx/sites-available/quadrum
upstream app_server {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    # Redirect all HTTP to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL certificates (obtain via Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # HSTS — Django (not this proxy) is the single source of HSTS.
    # Django's SecurityMiddleware sends Strict-Transport-Security (SECURE_HSTS_SECONDS=300).
    # Do NOT add the header here. Once verified, update Django settings only.

    # Static files (optional — WhiteNoise handles these)
    location /static/ {
        alias /opt/quadrum/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }

    # Media files
    location /media/ {
        alias /opt/quadrum/media/;
    }

    location / {
        proxy_pass http://app_server;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Trusted proxy headers
        proxy_redirect off;
        proxy_read_timeout 90;
    }
}
```

Enable and reload:
```bash
# Conditional (Ubuntu/Debian):
# sudo ln -s /etc/nginx/sites-available/quadrum /etc/nginx/sites-enabled/
# sudo nginx -t
# sudo systemctl reload nginx
```

### Apache Configuration (conditional)

```apache
# /etc/apache2/sites-available/quadrum.conf (Ubuntu/Debian)
# or /etc/httpd/conf.d/quadrum.conf (AlmaLinux/RHEL)

<VirtualHost *:80>
    ServerName yourdomain.com
    ServerAlias www.yourdomain.com
    Redirect permanent / https://yourdomain.com/
</VirtualHost>

<VirtualHost *:443>
    ServerName yourdomain.com
    ServerAlias www.yourdomain.com

    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/yourdomain.com/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/yourdomain.com/privkey.pem

    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/

    # Trusted proxy headers
    ProxyVia On
    RequestHeader set X-Forwarded-Proto "https" env=HTTPS

    # Static files (optional — WhiteNoise handles these)
    Alias /static/ /opt/quadrum/staticfiles/
    <Directory /opt/quadrum/staticfiles/>
        Require all granted
    </Directory>

    # HSTS — Django sends this header via SecurityMiddleware (SECURE_HSTS_SECONDS).
    # Do NOT add it here to avoid duplication. Once verified, change Django settings only.
</VirtualHost>
```

Enable and reload:
```bash
# Conditional (Ubuntu/Debian):
# sudo a2enmod ssl proxy proxy_http headers
# sudo a2ensite quadrum
# sudo systemctl reload apache2
```

---

## 11. HTTPS, Trusted Proxy, Allowed Hosts, CSRF Origins, Secure Cookies

### HTTPS

> ⚠️ **Your organization may not provide a public domain name, SSL certificate, or access to ports 80/443.** Confirm these requirements with the deployment owner before enabling HTTPS redirect and HSTS. If a domain or certificate is unavailable, skip the HTTPS redirect and use only the reverse proxy for internal testing.

Obtain certificates using Let's Encrypt (only if a public domain is available):
```bash
# Conditional (Ubuntu/Debian):
# sudo apt install certbot python3-certbot-nginx  # or python3-certbot-apache
# sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
# sudo certbot renew --dry-run  # test auto-renewal
```

### HTTPS vs Internal Demo (without HTTPS)

If no domain or SSL certificate is available:

- **Skip HTTPS redirect and HSTS.** Do not use `SECURE_SSL_REDIRECT = True` (or set it to `False` in settings for internal demo only — but note that the production settings enforce `True` when `DEBUG=False`).
- **Do not configure nginx/Apache SSL blocks.** Use a plain HTTP reverse proxy or access Gunicorn directly (e.g., `gunicorn --bind 0.0.0.0:8000`) for local/network testing only.
- **Keep `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` disabled** for internal HTTP-only testing, but note these are enabled in production settings (`DEBUG=False`).
- **Keep `SECURE_PROXY_SSL_HEADER` disabled** unless a trusted proxy actually forwards HTTPS headers.

If HTTPS **is** available:

- Confirm `ALLOWED_HOSTS` matches the domain.
- Confirm `CSRF_TRUSTED_ORIGINS` includes `https://` origins.
- Confirm SSL certificate is installed (`/etc/letsencrypt/live/...`).
- Confirm ports 80 and 443 are open.
- Only then should `SECURE_SSL_REDIRECT = True` and HSTS headers be active.

### Trusted Proxy Headers

When using a reverse proxy (nginx/Apache), configure Django's
`SECURE_PROXY_SSL_HEADER` in settings. **Only use this when a trusted
local proxy is configured**; without it, the header could be forged by
untrusted clients.

```python
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

This setting is **already enabled** in production mode (`DEBUG=False`).
Only rely on it when nginx/Apache (or another trusted proxy) is in front
of Gunicorn and forwards the `X-Forwarded-Proto: https` header.

### ALLOWED_HOSTS

Set `ALLOWED_HOSTS` to your domain names:
```
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

### CSRF_TRUSTED_ORIGINS

Set `CSRF_TRUSTED_ORIGINS` to your HTTPS origins:
```
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### Secure Cookies

When `DEBUG=False`, the following are **already enabled** in settings:
- `SESSION_COOKIE_SECURE = True`
- `CSRF_COOKIE_SECURE = True`

These ensure cookies are only sent over HTTPS.

### HSTS (Django is the single source; proxy does NOT duplicate)

Django's `SecurityMiddleware` sends `Strict-Transport-Security` when `SECURE_HSTS_SECONDS > 0` (currently 300 sec in production). The nginx/Apache configurations above intentionally do NOT include the header, avoiding duplication.

Before increasing HSTS:
1. Verify HTTPS works (`curl -v https://yourdomain.com/`).
2. Confirm `SECURE_SSL_REDIRECT` and `SECURE_PROXY_SSL_HEADER` are correct.
3. Confirm domain and SSL certificate are stable.

Only after verification should you:
- Change Django's `SECURE_HSTS_SECONDS` to 31536000 (1 year).
- Add `SECURE_HSTS_PRELOAD = True` (only if submitting to preload list).
- Add `SECURE_HSTS_INCLUDE_SUBDOMAINS = True` (already enabled in settings; verify before relying on it).

**Do not submit to the HSTS preload list** until HTTPS is verified.

---

## 12. Service Manager Configuration

### systemd (conditional — most modern distros: Ubuntu, AlmaLinux, Debian)

Create a service file:
```ini
# /etc/systemd/system/quadrum.service
[Unit]
Description=quadrum Gunicorn
After=network.target

[Service]
User=quadrum
Group=quadrum
WorkingDirectory=/opt/quadrum
EnvironmentFile=/opt/quadrum/.env
ExecStart=/opt/quadrum/.venv/bin/gunicorn config.wsgi:application \
    --workers 3 \
    --bind 127.0.0.1:8000
Restart=always
RestartSec=5
KillSignal=SIGQUIT
TimeoutStopSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable quadrum
sudo systemctl start quadrum
sudo systemctl status quadrum
```

### OpenRC (conditional — Alpine Linux, Devuan)

Create a service script:
```bash
# /etc/init.d/quadrum
#!/sbin/openrc-run

description="quadrum Gunicorn"
command="/opt/quadrum/.venv/bin/gunicorn"
command_args="config.wsgi:application --workers 3 --bind 127.0.0.1:8000"
command_user="quadrum:quadrum"
directory="/opt/quadrum"
pidfile="/var/run/quadrum.pid"
output_log="/var/log/quadrum/output.log"
error_log="/var/log/quadrum/error.log"
depend() {
    need net
    use postgresql
}
```

Enable and start:
```bash
sudo chmod +x /etc/init.d/quadrum
sudo mkdir -p /var/log/quadrum
sudo chown quadrum:quadrum /var/log/quadrum
sudo rc-update add quadrum default
sudo rc-service quadrum start
sudo rc-service quadrum status
```

---

## 13. Inspecting Logs

### Application Logs (stdout/stderr)

```bash
# systemd
sudo journalctl -u quadrum -f

# OpenRC
sudo tail -f /var/log/quadrum/error.log
sudo tail -f /var/log/quadrum/output.log
```

### Gunicorn Access Logs

Add `--access-logfile -` to Gunicorn args to log to stdout, or:
```bash
--access-logfile /var/log/quadrum/access.log --error-logfile /var/log/quadrum/error.log
```

### Web Server Logs

```bash
# nginx (conditional)
# sudo tail -f /var/log/nginx/quadrum_access.log
# sudo tail -f /var/log/nginx/quadrum_error.log

# Apache (conditional)
# sudo tail -f /var/log/apache2/quadrum_access.log
# sudo tail -f /var/log/apache2/quadrum_error.log
```

> ⚠️ **Do not log sensitive data** (passwords, session cookies, secret keys).
> The application logging is configured to avoid exposing these.

---

## 14. Backing Up PostgreSQL

### Create a Backup

Use `PGPASSWORD` or `.pgpass` for non-interactive authentication:

```bash
# With environment variable (temporary, not committed)
export PGPASSWORD="your-db-password"

# Create backup
pg_dump -U quadrum -h localhost quadrum > backup_$(date +%F).sql

echo "Backup created: backup_$(date +%F).sql (exit code: $?)"
# Verify the file exists and is non-empty:
ls -lh backup_$(date +%F).sql
```

> ⚠️ **Do not include `PGPASSWORD` in version control or logs.** For automated backups, use a `.pgpass` file (`chmod 600`) or a dedicated PostgreSQL user with restricted access.

### Verify a Backup Can Be Restored

```bash
# Restore from backup
createdb -U quadrum -h localhost quadrum_restore_test
psql -U quadrum -h localhost quadrum_restore_test < backup_2024-01-01.sql

# Verify data integrity (compare row counts or checksums)
psql -U quadrum -h localhost -c "SELECT count(*) FROM frontend_sale;"
psql -U quadrum -h localhost -c "SELECT count(*) FROM frontend_product;"

# Clean up test database
dropdb -U quadrum -h localhost quadrum_restore_test
```

### Automated Backups (conditional — cron)

Use `.pgpass` or a dedicated PostgreSQL user with restricted access. Verify exit code and file creation:

```bash
# Example crontab entry (use .pgpass file, chmod 600; do NOT use PGPASSWORD in crontab directly)
# Verify pg_dump output SEPARATELY before gzip; record failures explicitly
0 2 * * * /usr/bin/pg_dump -U quadrum -h localhost -w quadrum > /tmp/quadrum_backup_$(date +\%F).sql 2>/tmp/backup_$(date +\%F).err; PG_EXIT=$?; if [ $PG_EXIT -ne 0 ]; then echo "FAIL: pg_dump exit code $PG_EXIT on $(date)" >> /var/log/quadrum/backup.log; cat /tmp/backup_$(date +\%F).err >> /var/log/quadrum/backup.log; rm -f /tmp/quadrum_backup_$(date +\%F).sql; else /usr/bin/gzip /tmp/quadrum_backup_$(date +\%F).sql; /usr/bin/mv /tmp/quadrum_backup_$(date +\%F).sql.gz /var/backups/quadrum_$(date +\%F).sql.gz; echo "SUCCESS: backup $(date +\%F) created, size: $(ls -lh /var/backups/quadrum_$(date +\%F).sql.gz | awk '{print $5}')" >> /var/log/quadrum/backup.log; ls -lh /var/backups/quadrum_$(date +\%F).sql.gz >> /var/log/quadrum/backup.log 2>&1; fi; /usr/bin/rm -f /tmp/backup_$(date +\%F).err
```

> ⚠️ Never commit `.pgpass` or backup scripts to version control. Always verify the backup file exists (`ls -lh`) and check the exit code (`echo $?`). A backup is only considered valid after a successful restore test on a separate database.

> ⚠️ Store backups on a separate volume or remote server.
> Never commit backups to version control.

---

## 15. Post-Deployment Acceptance Test

After deployment, verify the application is working:

```bash
# 1. Check Gunicorn is running
# Conditional:
# sudo systemctl status quadrum  # systemd
# sudo rc-service quadrum status  # OpenRC

# 2. Check HTTP response (requires application running; HTTPS tests require domain + SSL cert configured)
curl -I http://127.0.0.1:8000/health/
curl -I http://127.0.0.1:8000/login/
curl -I http://127.0.0.1:8000/dashboard/

# 3. Check HTTPS (ONLY if a domain + SSL certificate are available; skip entirely otherwise)
curl -I https://yourdomain.com/health/ || echo "HTTPS test skipped: no domain or SSL cert configured"
curl -I https://yourdomain.com/login/ || echo "HTTPS test skipped: no domain or SSL cert configured"

# 4. Verify static files are served (local or via proxy; works with or without HTTPS)
# Note: If no domain/SSL, verify the local static file path directly:
ls -l /opt/quadrum/staticfiles/css/reset.css || echo "Static file not found at expected path"
# Via proxy (only if domain configured):
# curl -I https://yourdomain.com/static/css/reset.css || echo "Static file via proxy not verified"

# 5. Check admin login page loads (local only; via proxy only if configured)
curl -I http://127.0.0.1:8000/admin/

# 6. Verify security headers (ONLY after HTTPS verified and HSTS active; skip for internal demo)
# If HSTS not activated: expect no header (as shown by the || echo fallback)
curl -I https://yourdomain.com/ 2>/dev/null | grep -i "strict-transport-security" || echo "HSTS header not found (expected if HSTS not yet activated or no HTTPS)"
curl -I https://yourdomain.com/ 2>/dev/null | grep -i "x-frame-options" || echo "X-Frame-Options header not found"

# 7. Check HTTPS redirect (ONLY if HTTPS is configured with redirect enabled; skip for internal demo without HTTPS)
# If redirect is not configured (no HTTPS), expect no 301/302 from HTTP.
curl -I http://yourdomain.com/ 2>/dev/null | grep "301\|302" || echo "No HTTPS redirect found (expected for internal demo without HTTPS)"
```

---

## 16. Release Rollback and Non-Backward-Compatible Migrations

### Rolling Back an Application Release

To roll back to a previous release, select the previous Git tag or commit, then reinstall dependencies and restart:

```bash
cd /opt/quadrum

# Select the previous release tag (or commit hash)
# Example: git checkout v1.0.0  OR  git checkout <previous-commit-hash>
# IMPORTANT: "git pull origin main" does NOT restore a previous version.
# You must use "git checkout <tag>" or "git reset --hard <commit>".

# Reinstall dependencies if requirements changed
source .venv/bin/activate
pip install -r requirements.txt

# Restart without running migrations (do not use "python manage.py migrate" to rollback)
# If migrations are backward-compatible, you can migrate backward explicitly:
# python manage.py migrate <app_name> <previous_migration_number>

# Collect static files if they changed
python manage.py collectstatic --noinput

# Restart the service
# Conditional (systemd):
# sudo systemctl restart quadrum
# Conditional (OpenRC):
# sudo rc-service quadrum restart
```

> ⚠️ **Never rely on `python manage.py migrate` without an explicit target to roll back.** Without a target, `migrate` applies pending migrations forward, not backward. For backward migrations, specify the previous migration number (e.g., `python manage.py migrate frontend 0001`). For destructive (non-backward-compatible) migrations, the only safe rollback is to restore from a database backup (see below).

### Handling Non-Backward-Compatible Migrations

> ⚠️ **Critical Rule**: Never run a migration that cannot be rolled back
> without data loss. Use separate migration steps for schema changes and
> data migrations.

If a migration is **forward-only** (e.g., data is dropped/removed):

1. **Take a full backup before applying**:
   ```bash
   pg_dump -U quadrum -h localhost quadrum > pre_migration_backup.sql
   ```

2. **Apply the migration during a maintenance window**:
   ```bash
   # Put up a maintenance page
   # Apply the migration
   python manage.py migrate <app_name> <migration_name>
   ```

3. **If rollback is needed**:
   ```bash
   # Restore from backup (the only safe option for destructive migrations)
   createdb -U quadrum -h localhost quadrum_rollback
   psql -U quadrum -h localhost quadrum_rollback < pre_migration_backup.sql
   ```

4. **Never combine schema and destructive data changes in a single migration**.

---

## OS-Specific Package Installation Commands

These are **conditional** and depend on the server's Linux distribution.

### Ubuntu / Debian (APT)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip postgresql nginx

# Let's Encrypt
sudo apt install -y certbot python3-certbot-nginx
# or for Apache:
# sudo apt install -y certbot python3-certbot-apache
```

### AlmaLinux / RHEL (DNF)

```bash
sudo dnf install -y python3 python3-pip postgresql-server nginx

# Optionally enable EPEL for additional packages
sudo dnf install -y epel-release

# Let's Encrypt
sudo dnf install -y certbot python3-certbot-apache
```

### Alpine Linux (APK + OpenRC)

```bash
sudo apk add python3 py3-pip postgresql nginx openrc
# Note: Alpine does not support systemd; uses OpenRC as shown above
```

> ⚠️ **This project has NOT been tested on Alpine, AlmaLinux, or any specific
> Linux distribution. Adapt the commands above based on your OS.**

---

## Summary Checklist

- [ ] PostgreSQL installed and database created
- [ ] Python virtual environment created and activated
- [ ] Dependencies installed from `requirements.txt`
- [ ] `.env` file created with production values
- [ ] `DJANGO_SECRET_KEY` generated with `secrets` module
- [ ] `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` set
- [ ] `DATABASE_URL` or `DB_*` variables set for PostgreSQL
- [ ] Django checks pass: `python manage.py check`
- [ ] Production checks reviewed: `python manage.py check --deploy`
- [ ] Migrations applied: `python manage.py migrate --noinput`
- [ ] Static files collected: `python manage.py collectstatic --noinput --clear`
- [ ] Gunicorn tested manually
- [ ] Reverse proxy (nginx/Apache) configured and tested
- [ ] HTTPS certificates obtained and configured
- [ ] Service manager configured (systemd or OpenRC)
- [ ] Backups tested
- [ ] Post-deployment acceptance tests pass
