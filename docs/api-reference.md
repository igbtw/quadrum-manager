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
| `items` | array | No (defaults to `[]`) | A non-array value is rejected with `400` |
| `items[].product_id` | positive JSON integer | Yes | Integer `> 0` (booleans, floats, strings, `null`, `0`, and negatives rejected); must reference an existing, `active` product |
| `items[].quantity` | positive JSON integer | Yes | Integer `> 0` (booleans, floats including `2.0`, strings, `null`, `0`, and negatives rejected); a **missing** quantity is rejected |

Both POS endpoints share one strict validator (`_validate_pos_items` in
`frontend/views.py`). `product_id` and `quantity` must be JSON integers, so
`bool` is rejected despite being an `int` subclass, and values are never coerced
or truncated. A malformed identifier or quantity produces `400`; a *valid*
positive id that matches no active product produces `404`, preserving the
distinction between the two.

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
| `400` | Body is not valid JSON | `{"error": "Invalid JSON body"}` |
| `400` | Body is not a JSON object | `{"error": "Invalid request body"}` |
| `400` | `items` is not an array | `{"error": "Invalid items"}` |
| `400` | An item is not an object | `{"error": "Invalid item"}` |
| `400` | `product_id` is not a positive JSON integer | `{"error": "Invalid product_id"}` |
| `400` | `quantity` is missing or not a positive JSON integer | `{"error": "Invalid quantity"}` |
| `400` | Unexpected server-side error (logged; see note) | `{"error": "Calculation error"}` |
| `404` | A valid positive product id does not exist or is inactive | `{"error": "Product 99999 not found"}` |
| `302` | Unauthenticated | Redirect to `/login/` |
| `405` | Authenticated non-POST | Django method-not-allowed |

An empty `items` list returns `200 {"total": "0"}`.

Success example (product price `5.00`, quantity `2`):

```json
{"total": "10.00"}
```

Error examples:

```json
{"error": "Invalid quantity"}
```

```json
{"error": "Product 99999 not found"}
```

**Error disclosure:** unexpected exceptions are logged server-side via
`logger.exception` and returned to the client as the generic
`{"error": "Calculation error"}` with no exception text. The raw exception
message is never sent. (Note: this path currently returns HTTP `400`; returning
`400` for an unexpected server-side failure may merit a future API-contract
review, but the code was not changed here.)

**Side effects:** none.

**Implementation and tests:** `api_pos_calculate` and `_validate_pos_items` in
`frontend/views.py`. Validation is covered by `PosApiValidationTests` in
`frontend/tests/test_regressions.py` (`test_calculate_valid_total`,
`test_calculate_ignores_client_price`,
`test_calculate_rejects_invalid_quantities`,
`test_calculate_rejects_missing_quantity`,
`test_calculate_rejects_invalid_product_ids`,
`test_calculate_rejects_malformed_items`,
`test_calculate_missing_product_returns_404`,
`test_calculate_unexpected_error_hides_internal_details`,
`test_calculate_malformed_json_returns_controlled_error`), alongside
`test_api_pdv_calcular_real_product`, `test_api_pdv_calcular_bad_id`
(`frontend/tests/test_regressions.py`), and `test_invalid_product_id_in_api`
(`frontend/tests/test_auth_security.py`).

## Endpoint 2: Finalize sale

`POST /api/pdv/finalizar/`

Creates and completes a sale (with idempotency), reducing stock and, for
on-account sales with a customer, creating a receivable.

### Request schema

| Field | Type | Required | Notes |
|---|---|---|---|
| `items` | array | Yes (must be non-empty) | Each line needs `product_id` and `quantity` |
| `items[].product_id` | positive JSON integer | Yes | Integer `> 0`; used to load the product, price comes from the DB |
| `items[].quantity` | positive JSON integer | Yes | Integer `> 0` (booleans, floats, strings, `null`, `0`, and negatives rejected); a **missing** quantity is rejected |
| `items[].unit_price` | number | No | **Ignored**; the server always uses `Product.price` |
| `customer_id` | integer | No | Must reference an existing `active` `Person`; required only to attach a customer/receivable |
| `payment_method` | string | No (default `"CASH"`) | Whitelisted: only `CASH`, `DEBIT`, `CREDIT`, `PIX`, `ON_ACCOUNT` (exact codes) |
| `idempotency_key` | string | Yes | 1–255 chars matching `^[A-Za-z0-9_-]+$` |

`items[].product_id` follows the same rule as the calculation endpoint (positive
JSON integer; booleans, floats, strings, `null`, zero, and negatives rejected).
Item and `payment_method` validation runs **before** the request fingerprint is
computed and **before** any database write; the fingerprint and the persisted
`SaleItem` rows are built from the same normalized values, so a quantity cannot
be fingerprinted differently from how it is stored.

`payment_method` uses the exact five codes declared by `Sale.PAYMENT_METHODS`
(`CASH`, `DEBIT`, `CREDIT`, `PIX`, `ON_ACCOUNT`). Unknown values, different
casing (`cash`), and values with leading/trailing whitespace (`"CASH "`) are
rejected with `400` rather than normalized into a valid classification.

A customer is only mandatory in practice for `ON_ACCOUNT`; an `ON_ACCOUNT` sale
without a customer completes but creates no receivable. (Whether `ON_ACCOUNT`
should require a customer is a separate, unresolved product decision and is not
enforced by this endpoint.)

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
| `400` | Malformed item: `items` not an array, an item not an object, or a non-positive/invalid `product_id` or `quantity` | `Invalid items` / `Invalid item` / `Invalid product_id` / `Invalid quantity` |
| `400` | `payment_method` not one of the five declared codes | `Invalid payment method` |
| `400` | Missing/empty key, longer than 255 chars, or containing disallowed characters | `Invalid idempotency key` |
| `404` | `customer_id` provided but no active `Person` | `Customer not found` |
| `403` | Key exists but belongs to another user (including legacy `NULL` responsible) | `Idempotency key not authorized` |
| `409` | Key exists, sale is `COMPLETED`, and fingerprint differs | `Key conflict: request data changed` |
| `409` | Key exists, sale is `COMPLETED`, but stored fingerprint is empty | `Key conflict: existing sale without verification fingerprint` |
| `409` | Key exists and the sale is not `COMPLETED` | `Checkout attempt already in progress or incomplete` |
| `500` | Request body is not valid JSON, is not valid UTF-8, or decodes to a non-object (see note) | `Internal error finalizing sale` |
| `500` | Unexpected error or insufficient stock (`ValueError` not specially handled) | `Internal error finalizing sale` |
| `302` | Unauthenticated | Redirect to `/login/` |
| `405` | Authenticated non-POST | Django method-not-allowed |

Note: insufficient stock surfaces as `500` because `reduce_stock()` raises
`ValueError`, which the view does not map to a client error. This is a verified
behavior gap, not an intended contract.

**Malformed-JSON behavior (current, verified):** `api_pos_finalize` does **not**
catch `json.JSONDecodeError`/`UnicodeDecodeError` separately (unlike
`api_pos_calculate`, which returns `400 {"error": "Invalid JSON body"}`). A
malformed body, an invalid UTF-8 body, or valid JSON that is not an object
(e.g. a top-level array, string, or number) raises inside
`json.loads`/`data.get(...)` and is caught by the view's generic
`except Exception` handler (`frontend/views.py`), which logs via
`logger.exception` and returns **HTTP `500`** with
`{"error": "Internal error finalizing sale"}` and no exception text. No test
currently covers this path. This is a client-input error returned as a generic
server error and is flagged as a possible future API-correctness fix (it was not
changed here).

### Idempotency, replay, and conflicts

The request fingerprint is a SHA-256 over a normalized structure of
`sorted([(product_id, quantity)])`, `customer_id`, and `payment_method`
(`unit_price` and item order are excluded). The `product_id`/`quantity` pairs
come from the validated items, so the fingerprint always reflects the exact
integers that will be persisted. Rules:

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

Input validation is covered by `PosApiValidationTests`
(`frontend/tests/test_regressions.py`): invalid quantities, product ids, and
payment methods produce `400` with no `Sale`, `SaleItem`, `StockMovement`, or
`AccountReceivable` written and no stock change
(`test_finalize_rejects_invalid_quantities_without_writes`,
`test_finalize_rejects_missing_quantity_without_writes`,
`test_finalize_rejects_invalid_product_ids_without_writes`,
`test_finalize_rejects_invalid_payment_methods_without_writes`); all five
declared payment methods are accepted
(`test_finalize_accepts_all_declared_payment_methods`); and a fractional
quantity is never truncated for fingerprinting
(`test_finalize_fingerprint_not_truncated`,
`test_finalize_float_replay_not_treated_as_equivalent`).

### Client mismatch (current limitation)

The bundled template `frontend/templates/frontend/point_of_sale.html` builds its
payload with Portuguese field names (`itens`, `produto_id`, `forma_pagamento`,
`cliente_id`) and calls undefined helpers such as `quadrum.showToast`. The
endpoint expects the English fields documented above, so the current UI cannot
successfully finalize a sale through this endpoint. The frontend defect is out
of scope for this documentation phase and must not be treated as an operational
feature. The contract above is what the server actually accepts, verified by the
tests cited.
