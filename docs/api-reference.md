# quadrum API Reference

quadrum exposes two JSON endpoints for the point-of-sale (POS) workflow. Both
live in `frontend/views.py` and are registered in `frontend/urls.py` under
`app_name = 'frontend'`, which `config/urls.py` includes at the site root.

**The HTTP paths are intentionally kept in Portuguese for backwards
compatibility and must not be renamed.** The Python view names and Django URL
names are English and are separate concepts:

| HTTP path | view function | URL name |
|---|---|---|
| `/api/pdv/calcular/` | `api_pos_calculate` | `frontend:api_pos_calculate` |
| `/api/pdv/finalizar/` | `api_pos_finalize` | `frontend:api_pos_finalize` |

Both endpoints are `POST`-only and both are protected. Verified sources:
`frontend/views.py`, `frontend/urls.py`, `frontend/urls.py` routing,
`frontend/models.py`, `frontend/services.py`, and the tests under
`frontend/tests/`.

Related documents: [Business flows](business-flows.md) ·
[Data model](data-model.md) · [Architecture](architecture.md) ·
[Documentation index](index.md).

## Shared behavior: authentication, CSRF, and methods

- **Authentication.** Both views are decorated with `@login_required`. An
  unauthenticated request is redirected to `LOGIN_URL` (`/login/`) with status
  `302`, not a `401`/`403`. Verified by
  `test_api_pdv_requires_login_and_ignores_client_price`, which posts a finalize
  request anonymously and asserts `302`.
- **Methods.** Both views are wrapped with `@require_http_methods(["POST"])`.
  Because the decorators are applied as `@login_required` over
  `@require_http_methods`, an unauthenticated non-POST request redirects first; an
  authenticated non-POST request returns `405`. Only `POST` is documented here.
- **CSRF.** Django's `CsrfViewMiddleware` is active. Real browser requests must
  send a CSRF token, either as the `X-CSRFToken` header or the
  `csrfmiddlewaretoken` form field. The bundled POS template sends the cookie
  value via the `X-CSRFToken` header. In the test suite the default
  `Client(enforce_csrf_checks=False)` is used, so the tests pass
  `HTTP_X_CSRFTOKEN='fake'` without real token validation;
  `test_csrf_missing_on_form_post` confirms CSRF is enforced when
  `enforce_csrf_checks=True` (for the product form, not the JSON endpoints).
- **Content type.** Both views call `json.loads(request.body)` directly, so the
  body must be JSON. Request content type is not checked explicitly.
- **Response envelope.** There is no uniform envelope. Calculate returns
  `{"total": ...}`. Finalize returns `{"success": true, ...}` on success and
  `{"error": "..."}` on failure.

## Endpoint 1: Calculate total

`POST /api/pdv/calcular/`

Computes a cart total from product ids and quantities. It is read-only.

### Request schema

| Field | Type | Required | Notes |
|---|---|---|---|
| `items` | array | No (defaults to `[]`) | List of line objects |
| `items[].product_id` | integer | Yes (for a meaningful result) | Must reference an existing, `active` product |
| `items[].quantity` | integer | No (defaults to `1`) | Multiplied by the product price; **not validated** |

Client-supplied prices are ignored; only `Product.price` from the database is
used.

Minimal request:

```http
POST /api/pdv/calcular/
Content-Type: application/json
X-CSRFToken: <csrf-token>
Cookie: sessionid=<session-id>

{"items": [{"product_id": 12, "quantity": 2}]}
```

### Responses

| Status | When | Body |
|---|---|---|
| `200` | Items resolved | `{"total": "10.00"}` (the total is a string) |
| `404` | A product id does not exist or is inactive | `{"error": "Product 99999 not found"}` |
| `400` | Malformed JSON or any unexpected error | `{"error": "Calculation error: <message>"}` |
| `302` | Unauthenticated | Redirect to `/login/` |
| `405` | Authenticated non-POST | Django method-not-allowed |

An empty `items` list returns `200 {"total": "0"}`.

Success example (product price `5.00`, quantity `2`):

```json
{"total": "10.00"}
```

Error example:

```json
{"error": "Product 99999 not found"}
```

**Side effects:** none.

**Implementation and tests:** `api_pos_calculate` in `frontend/views.py`;
`test_api_pdv_calcular_real_product`, `test_api_pdv_calcular_bad_id`
(`frontend/tests/test_regressions.py`), `test_invalid_product_id_in_api`
(`frontend/tests/test_auth_security.py`). Quantity validation is absent in the
source and has no test.

## Endpoint 2: Finalize sale

`POST /api/pdv/finalizar/`

Creates and completes a sale (with idempotency), reducing stock and, for
on-account sales with a customer, creating a receivable.

### Request schema

| Field | Type | Required | Notes |
|---|---|---|---|
| `items` | array | Yes (must be non-empty) | Each line needs `product_id` and `quantity` |
| `items[].product_id` | integer | Yes | Used to load the product; price comes from the DB |
| `items[].quantity` | integer | Yes | Used for `SaleItem.quantity` and stock reduction; not range-validated in the view |
| `items[].unit_price` | number | No | **Ignored**; the server always uses `Product.price` |
| `customer_id` | integer | No | Must reference an existing `active` `Person`; required only to attach a customer/receivable |
| `payment_method` | string | No (default `"CASH"`) | **Not validated** against the model choices; any string is stored |
| `idempotency_key` | string | Yes | 1–255 chars matching `^[A-Za-z0-9_-]+$` |

Accepted `payment_method` values used elsewhere in the app are `CASH`, `DEBIT`,
`CREDIT`, `PIX`, and `ON_ACCOUNT`, but this endpoint does not enforce that list.
A customer is only mandatory in practice for `ON_ACCOUNT`; an `ON_ACCOUNT` sale
without a customer completes but creates no receivable.

Minimal request:

```http
POST /api/pdv/finalizar/
Content-Type: application/json
X-CSRFToken: <csrf-token>
Cookie: sessionid=<session-id>

{
  "items": [{"product_id": 12, "quantity": 2}],
  "customer_id": 3,
  "payment_method": "CASH",
  "idempotency_key": "checkout-8f2c1a4e"
}
```

### Success response

```json
{"success": true, "codigo": "VEN-000042", "message": "Sale completed"}
```

`codigo` is the `Sale.code`. The same body is returned for a successful idempotent
replay (see below).

### Error responses

| Status | When | Body `error` |
|---|---|---|
| `400` | `items` empty or absent | `Empty cart` |
| `400` | Missing/empty key, longer than 255 chars, or containing disallowed characters | `Invalid idempotency key` |
| `404` | `customer_id` provided but no active `Person` | `Customer not found` |
| `403` | Key exists but belongs to another user (including legacy `NULL` responsible) | `Idempotency key not authorized` |
| `409` | Key exists, sale is `COMPLETED`, and fingerprint differs | `Key conflict: request data changed` |
| `409` | Key exists, sale is `COMPLETED`, but stored fingerprint is empty | `Key conflict: existing sale without verification fingerprint` |
| `409` | Key exists and the sale is not `COMPLETED` | `Checkout attempt already in progress or incomplete` |
| `500` | Unexpected error or insufficient stock (`ValueError` not specially handled) | `Internal error finalizing sale` |
| `302` | Unauthenticated | Redirect to `/login/` |
| `405` | Authenticated non-POST | Django method-not-allowed |

Note: insufficient stock surfaces as `500` because `reduce_stock()` raises
`ValueError`, which the view does not map to a client error. This is a verified
behavior gap, not an intended contract.

### Idempotency, replay, and conflicts

The request fingerprint is a SHA-256 over a normalized structure of
`sorted([(product_id, quantity)])`, `customer_id`, and `payment_method`
(`unit_price` and item order are excluded). Rules:

- **Equivalent retry** (same key, same fingerprint, existing sale `COMPLETED`):
  `200` with the original `codigo`; no writes.
- **Key reused with different data**: `409 Key conflict: request data changed`.
- **Different user, same key**: `403 Idempotency key not authorized`. Ownership
  is `(responsible_id or 0) == request.user.id`.
- **Legacy completion without fingerprint**: `409 Key conflict: existing sale
  without verification fingerprint`.
- **Concurrent insert collision**: the `IntegrityError` handler re-reads the sale
  and applies the same rules; if no record exists, `500`.

### Side effects

On a newly created sale (all within one `transaction.atomic()` block in the
view):

- one `Sale` (`status='COMPLETED'`, `completed_at` set, `responsible` set);
- one `SaleItem` per line with `unit_price` taken from `Product.price`;
- `Product.stock_quantity` reduced per line, each with a `SALE` `StockMovement`;
- for `ON_ACCOUNT` sales with a customer, one `AccountReceivable`.

No `Payment` is created. The endpoint never trusts a client price. These
behaviors are verified by `test_duplicate_finalization_idempotent`,
`test_idempotency_ownership_and_conflict`,
`test_api_pdv_requires_login_and_ignores_client_price`,
`test_missing_fingerprint_returns_409`,
`test_integrityerror_without_matching_record_returns_500`, and
`test_unexpected_exception_returns_generic_500` in
`frontend/tests/test_regressions.py`, plus `test_sale_confirm_items_stock` in
`frontend/tests/test_integration.py`.

### Client mismatch (current limitation)

The bundled template `frontend/templates/frontend/point_of_sale.html` builds its
payload with Portuguese field names (`itens`, `produto_id`, `forma_pagamento`,
`cliente_id`) and calls undefined helpers such as `quadrum.showToast`. The
endpoint expects the English fields documented above, so the current UI cannot
successfully finalize a sale through this endpoint. The frontend defect is out
of scope for this documentation phase and must not be treated as an operational
feature. The contract above is what the server actually accepts, verified by the
tests cited.
