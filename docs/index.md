# quadrum Documentation

This is the entry point for the quadrum documentation. It links to the
documents that currently exist in the repository and explains who each one is
for.

## Project overview

- [README](../README.md) — what quadrum is, the technology stack, a short
  local quick start, and the feature summary. Start here if you are new to the
  project.

## Architecture

- [Architecture](architecture.md) — the Django project and application layout,
  URL routing, request flow, data model summary, template discovery, and the
  routing contract. Intended for contributors and reviewers who need to
  understand how the pieces fit together.

## Developer references

- [Data model](data-model.md) — the database schema: entities, relationships,
  constraints, invariants, transactions, and safe migration practices.
- [Business flows](business-flows.md) — how the point-of-sale, inventory,
  payment, receivable, dashboard, and reporting workflows actually run through
  the views, services, and models.
- [API reference](api-reference.md) — the two POS JSON endpoints
  (`/api/pos/calculate/`, `/api/pos/finalize/`), including request/response
  schemas, idempotency, and error codes.

## Development and contributions

- [Contributing](../CONTRIBUTING.md) — development setup, the checks to run
  before proposing changes, and project guidelines. Intended for anyone
  preparing a contribution.

## Deployment and operations

- [Deployment](../DEPLOYMENT.md) — the canonical operations guide: runtime
  requirements, environment variables, database configuration, static files,
  WSGI server, reverse proxy, HTTPS, service managers, backups, and rollback.
  Intended for operators deploying or maintaining a quadrum instance.

> Additional developer documentation (security, frontend, testing, and
> configuration) will be added incrementally.
