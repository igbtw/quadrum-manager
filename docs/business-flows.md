# quadrum Business Flows

This document traces the main workflows through the actual views, services,
models, and tests. Paths and symbol names are given so a reader can follow the
implementation in the repository.

Verified sources: `frontend/views.py`, `frontend/services.py`,
`frontend/models.py`, `frontend/forms.py`, `frontend/urls.py`,
`frontend/templates/frontend/point_of_sale.html`, and the tests under
`frontend/tests/`.

Related documents: [Data model](data-model.md) ·
[API reference](api-reference.md) · [Architecture](architecture.md) ·
[Documentation index](index.md).

## A. Point-of-sale calculation

**Entry point:** `POST /api/pdv/calcular/` → `frontend.views.api_pos_calculate`
(URL name `frontend:api_pos_calculate`).

**Ordered processing steps:**

1. `@login_required` and `@require_http_methods(["POST"])` gate the request.
2. `json.loads(request.body)` parses the body. Any parse failure is caught by the
   broad handler.
3. `items = data.get('items', [])` is read.
4. For each item: `product_id = item.get('product_id')` and
   `quantity = item.get('quantity', 1)`. The product is looked up with
   `Product.objects.get(pk=product_id, active=True)`.
5. If the product does not exist (or is inactive), the loop returns
   `404 {"error": "Product <id> not found"}`.
6. Otherwise the running total is increased by `product.price * Decimal(str(quantity))`.
7. The view returns `200 {"total": "<decimal>"}` — the total is a **string**.

**Functions and files:** `api_pos_calculate` in `frontend/views.py`; reads
`Product` from `frontend/models.py`.

**Price handling:** the endpoint never reads a client-supplied price. It sums
`Product.price` from the database. Client prices sent alongside are ignored.

**Database writes and side effects:** none. The endpoint is read-only.

**Validation and error paths:**

- Unknown/inactive product → `404` with `Product <id> not found`.
- Malformed JSON or any other exception → `400` with
  `Calculation error: <message>` (the raw exception string is included).
- Quantity is **not** validated: a missing quantity defaults to `1`, and
  zero/negative or non-numeric quantities are not rejected before use
  (a negative quantity simply reduces the total). This is an unverified edge
  case with no dedicated test.

**Tests:** `test_api_pdv_calcular_real_product` and `test_api_pdv_calcular_bad_id`
in `frontend/tests/test_regressions.py`; `test_invalid_product_id_in_api` in
`frontend/tests/test_auth_security.py`.

## B. Sale finalization

**Entry point:** `POST /api/pdv/finalizar/` → `frontend.views.api_pos_finalize`
(URL name `frontend:api_pos_finalize`).

**Ordered processing steps (verified against `frontend/views.py`):**

1. `@login_required` and `@require_http_methods(["POST"])` gate the request.
2. Parse the body with `json.loads`. Read `items`, `customer_id`,
   `payment_method` (default `"CASH"`), and `idempotency_key` (coerced to string
   and stripped).
3. Reject an empty cart: `400 {"error": "Empty cart"}`.
4. Validate the idempotency key (non-empty, `<= 255` chars, matching
   `^[A-Za-z0-9_-]+$`): otherwise `400 {"error": "Invalid idempotency key"}`.
5. Compute the request fingerprint (see [section C](#c-idempotency-and-retries)).
6. If `customer_id` is provided, resolve `Person.objects.get(pk=..., active=True)`;
   if not found, `404 {"error": "Customer not found"}`.
7. Open `transaction.atomic()` and look up an existing `Sale` by
   `idempotency_key`:
   - **Found, different owner** → `403 {"error": "Idempotency key not authorized"}`.
   - **Found, `COMPLETED`, fingerprint mismatch** → `409 {"error": "Key conflict: request data changed"}`.
   - **Found, `COMPLETED`, no fingerprint** → `409 {"error": "Key conflict: existing sale without verification fingerprint"}`.
   - **Found, `COMPLETED`, fingerprint match** → `200` replay with the existing
     `code` (no writes).
   - **Found, any other status** → `409 {"error": "Checkout attempt already in progress or incomplete"}`.
   - **Not found** → continue.
8. Create the `Sale` with `status='PENDING'`, `payment_method`, zero
   `subtotal`/`total`, the `idempotency_key`, and the `request_fingerprint`.
   `responsible` is the authenticated user.
9. Build `items_data` containing only `product_id` and `quantity` — any client
   `unit_price` is discarded here.
10. `create_sale_items(sale, items_data, user=...)`: for each item, lock the
    product, use `Product.price` as `unit_price`, create the `SaleItem`
    (subtotal computed in `SaleItem.save()`), and call `reduce_stock()` (which
    decrements stock and writes a `SALE` `StockMovement`).
11. Sum the item subtotals into `sale.subtotal` and `sale.total` and save
    (`update_fields=['subtotal', 'total', 'request_fingerprint']`).
12. `finalize_sale(sale, user=...)`: lock the sale, return early if already
    `COMPLETED`, otherwise set `status='COMPLETED'`, `completed_at=now`,
    `responsible`, save, and — for `ON_ACCOUNT` sales with a customer — create an
    `AccountReceivable` via `get_or_create` (`person`, `original_amount=total`,
    `due_date=completed_at.date()`, `status='PENDING'`).
13. Return `200 {"success": true, "codigo": sale.code, "message": "Sale completed"}`.

**Database writes and side effects:** one `Sale`, one `SaleItem` per line,
`Product.stock_quantity` decrements, one `SALE` `StockMovement` per line, and
(conditionally) one `AccountReceivable`. No `Payment` is created by this flow.

**Transactional guarantee:** the view wraps steps 7–13 in a single
`transaction.atomic()`, so on failure all of those writes roll back together.
This is a confirmed guarantee of the code path, not an assumption.

**Error handling and rollback:**

- `IntegrityError` (typically a concurrent insert of the same idempotency key) is
  caught, the sale is re-read by key, and the same ownership/fingerprint/status
  responses are produced (`403`/`409`/replay `200`). If no matching record exists,
  the view logs the exception and returns
  `500 {"error": "Internal error finalizing sale"}`.
- Any other exception is logged and returns the same generic `500` body with no
  internal detail.
- Note: `reduce_stock()` raising `ValueError` for insufficient stock is **not**
  mapped to a specific status. It falls through to the generic handler and
  returns `500`, even though the situation is a client-correctable condition.
  This is a verified behavior gap.

**Idempotency/ownership/conflict details** are in
[section C](#c-idempotency-and-retries).

**Tests:** `test_api_pdv_requires_login_and_ignores_client_price`,
`test_duplicate_finalization_idempotent`, `test_idempotency_ownership_and_conflict`,
`test_missing_fingerprint_returns_409`,
`test_integrityerror_without_matching_record_returns_500`, and
`test_unexpected_exception_returns_generic_500` in
`frontend/tests/test_regressions.py`;
`test_sale_confirm_items_stock` in `frontend/tests/test_integration.py`.

## C. Idempotency and retries

**Required key format:** non-empty, at most 255 characters, matching
`^[A-Za-z0-9_-]+$`. Validated in `api_pos_finalize`; an invalid key returns
`400 {"error": "Invalid idempotency key"}`. The database enforces uniqueness via
`Sale.idempotency_key`.

**Request fingerprint:** computed by the inner `_fingerprint()` helper over a
normalized structure:

- `items`: `sorted([ (int(product_id), int(quantity)) , ... ])` — item order is
  irrelevant and `unit_price` is excluded;
- `customer_id`: `int(customer_id)` or `None`;
- `payment_method`: the raw string.

The normalized dict is serialized with `json.dumps(..., sort_keys=True)` and
hashed with SHA-256. It is stored in `Sale.request_fingerprint`.

**Equivalent retry:** the same key with an equivalent payload (same items,
quantities, customer, and method) finds the existing `COMPLETED` sale with a
matching fingerprint and returns `200 {"success": true, "codigo": <code>,
"message": "Sale completed"}`. No new sale, stock movement, or item is written.
Verified by `test_duplicate_finalization_idempotent` (stock decremented exactly
once).

**Key reuse with different data:** the fingerprint differs → `409 {"error": "Key
conflict: request data changed"}`. Verified by `test_idempotency_ownership_and_conflict`.

**Ownership:** the view compares `(existing.responsible_id or 0)` with
`request.user.id`. A different user gets `403 {"error": "Idempotency key not
authorized"}`. A legacy sale with `responsible = NULL` evaluates to `0` and can
never match a real user id, so it is always treated as not authorized. Verified
by `test_idempotency_ownership_and_conflict`.

**Conflict/failure responses:**

| Situation | Status | Body `error` |
|---|---|---|
| Empty cart | 400 | `Empty cart` |
| Invalid key | 400 | `Invalid idempotency key` |
| Customer not found | 404 | `Customer not found` |
| Different owner | 403 | `Idempotency key not authorized` |
| Fingerprint mismatch | 409 | `Key conflict: request data changed` |
| Completed sale without fingerprint | 409 | `Key conflict: existing sale without verification fingerprint` |
| Key found but not completed | 409 | `Checkout attempt already in progress or incomplete` |
| Unexpected failure | 500 | `Internal error finalizing sale` |

**Unverified edge cases:** concurrent identical requests that arrive before either
commits rely on the unique index and the `IntegrityError` handler; the handler is
unit-tested by mocking `Sale.objects.create` to raise
(`test_integrityerror_without_matching_record_returns_500`) but is not exercised
under real concurrent load. Fingerprint collisions across differing requests are
not tested. `payment_method` is not validated against the model choices, so an
arbitrary string is accepted and stored.

## D. Inventory

**Adjustment entry point (UI):** `POST /inventory/` → `frontend.views.inventory`.

1. Reads `product_id`, `qty` (cast to `int`), and `reason` (default `''`).
2. Rejects `qty == 0` by raising `ValueError('Quantity zero')`.
3. Loads `Product.objects.get(pk=product_id, active=True)`.
4. Calls `services.adjust_stock(prod, qty, reason=..., user=...)`.
5. Any exception is caught and surfaced via `messages.error`; success shows a
   message and redirects to `frontend:inventory` (`/inventory/`).
6. The GET branch builds per-product inventory status (`OUT_OF_STOCK`, `LOW`,
   `NORMAL`), counts, and the retail value `price * stock_quantity`.

**`adjust_stock(product, qty, reason='', user=None)`** (`frontend/services.py`):
atomic; locks the product with `select_for_update()`; adds the signed `qty` to
`stock_quantity`; saves; writes an `ADJUSTMENT` `StockMovement` with the signed
quantity and the reason (default `Manual adjustment`). It does **not** check for
negative results — a large negative adjustment can hit the
`stock_non_negative` database constraint and raise, which the view reports as an
error. Verified by `test_inventory_adjustment_and_history` and
`test_failed_inventory_does_not_partial_update`.

**Stock reduction (sales):** `reduce_stock(product, qty, user=None, sale=None)`:
atomic; locks the product; raises `ValueError` if the result would be negative;
decrements and saves `stock_quantity`; writes a `SALE` `StockMovement` with
`quantity=-qty`. Called by `create_sale_items()` during finalization.

**Stock restoration on cancellation:** `cancel_sale(sale, user=None)`:

1. Atomic; locks the sale with `select_for_update()`.
2. If already `CANCELLED`, returns immediately (idempotent).
3. If not `COMPLETED`, raises `ValueError('Only completed sales can be
   cancelled.')`.
4. If the sale is `ON_ACCOUNT` with a customer and its receivable already has
   payments, raises `ValueError('Cannot cancel: recorded payments exist on the
   receivable account.')`.
5. Sets `status='CANCELLED'` and saves.
6. For `ON_ACCOUNT` sales, marks the receivable `CANCELLED` (the record is never
   deleted).
7. For each item, locks the product, restores `stock_quantity += quantity`, and
   writes a `RETURN` `StockMovement`.

**Stock movement semantics:** movements are an append-only audit trail with a
signed `quantity`. They preserve the ability to reconstruct how a product's stock
changed. `SALE` (negative), `RETURN` (positive), and `ADJUSTMENT` (signed) are
produced by services; `ENTRY`/`EXIT` are defined but unused by current code.
Movements reference the product with `PROTECT`, so a product with movement
history cannot be deleted.

**Tests:** `test_cancel_sale_idempotent_and_reversal`,
`test_cancel_rejected_if_payments_exist` in `frontend/tests/test_regressions.py`;
`test_inventory_adjustment_and_history`, `test_cancel_idempotent_and_rejected_with_payments`,
`test_failed_inventory_does_not_partial_update` in
`frontend/tests/test_integration.py`.

## E. Payment registration

**Entry point (UI):** `POST /finance/` → `frontend.views.finance`.

1. Binds `PaymentForm(request.POST)` (`fields = ['account_receivable', 'amount', 'method', 'notes']`).
2. On valid input, calls
   `register_payment(rc, amount, method=..., user=request.user, notes=...)`.
3. Success shows `Payment registered.`; failure shows `Please verify the payment.`.

**`register_payment(account_receivable, amount, method='CASH', user=None, notes='')`**
(`frontend/models.py`):

1. Opens `transaction.atomic()`.
2. Reloads and locks the receivable:
   `AccountReceivable.objects.select_for_update().get(pk=account_receivable.pk)`.
3. If `amount > rc.remaining_balance`, raises
   `ValueError('Payment exceeds remaining balance.')`.
4. Creates the `Payment` (which triggers `Payment.save()`'s status recalculation).
5. Calls `rc.update_status()` and saves `status`.

**Outstanding balance:** `remaining_balance` is `original_amount` minus the sum of
all payments, floored at zero. `amount_paid` aggregates payments with
`Sum('amount')`.

**Concurrency:** the receivable row is locked with `select_for_update()`, so
concurrent payments against the same receivable serialize on backends that
support row locking (PostgreSQL). On SQLite the lock is effectively ignored.
There is no application-level lock or retry loop.

**Overpayment / invalid amounts:**

- Overpayment is blocked by `PaymentForm.clean_amount()` (UI path),
  `Payment.clean()` (model `full_clean`), and `register_payment()` (service).
- Amounts below `0.01` are blocked by the field validator and the form, but
  **not** by `register_payment()` directly, because it does not run
  `full_clean()`.
- Verified by `test_payment_form_over_balance`, `test_payment_form_valid`,
  `test_payment_service_recalculates`, `test_receivable_partial_and_complete`,
  and `test_duplicate_payment_blocked`.

## F. Accounts receivable and cancellation

**Creation:** an `AccountReceivable` is created only by `finalize_sale()` for a
sale whose `payment_method == 'ON_ACCOUNT'` **and** which has a customer. An
`ON_ACCOUNT` sale without a customer completes and silently creates no
receivable. The original amount is the sale total and the due date is the
completion date.

**Status transitions (from `AccountReceivable.update_status()`):**

- `remaining_balance <= 0` → `PAID` (this check runs first, so a fully paid
  receivable is `PAID` even if past due).
- `due_date < today` and `remaining_balance > 0` → `OVERDUE`.
- `amount_paid > 0` (with a remaining balance, not past due) → `PARTIAL`.
- otherwise → `PENDING`.

The code supports a subset of possible transitions and recomputes status only
when a payment write occurs. There is no automatic job that periodically moves
receivables to `OVERDUE`; a receivable stays in its last computed status until
the next `register_payment()`/`Payment.save()`/`update_status()` call. The
dashboard and finance views filter on the stored `status` values
(`PENDING`, `PARTIAL`, `OVERDUE`), so this staleness also affects the aggregates.

**Cancellation restrictions:** only `COMPLETED` sales can be cancelled. An
`ON_ACCOUNT` sale whose receivable already has payments cannot be cancelled
(`ValueError`). Cancellation is idempotent for already-cancelled sales. On
cancellation the receivable is marked `CANCELLED` (never deleted) and stock is
restored with `RETURN` movements. Verified by
`test_cancel_rejected_if_payments_exist` and
`test_cancel_idempotent_and_rejected_with_payments`.

## G. Dashboard and reports

### Dashboard (`frontend.views.dashboard`, public)

Aggregates over the current date (`timezone.now().date()`):

- `vendas_dia` — count of `COMPLETED` sales created today.
- `faturamento_dia` — `Sum('total')` of `COMPLETED` sales today (defaults to `0.00`).
- `valor_receber` — `Sum('original_amount')` for receivables in
  `PENDING`/`PARTIAL`/`OVERDUE`. This uses the **original** amount, not the
  remaining balance (a simplification noted in a code comment).
- Low-stock count (active, `stock_quantity <= minimum_stock`, `> 0`) and
  out-of-stock count (active, `stock_quantity == 0`).
- Five most recent sales and five low-stock products.

Rendered with `frontend/templates/frontend/dashboard.html`. Verified in part by
`test_dashboard_sales_today` and `test_report_low_stock`.

### Reports (`frontend.views.reports`, protected)

- `vendas_periodo` — `COMPLETED` sales with `created_at__date >= today - 7 days`.
- `total_vendas_periodo` — `Sum('total')` over that period; `count_vendas_periodo`
  — its count.
- `best_selling` — top 5 products by `Sum('quantity')` over `SaleItem` rows whose
  sale is `COMPLETED`, grouped by `product__name`.
- `low_stock_count` — active products with `stock_quantity <= minimum_stock`.
- `receivable_total` — `Sum('original_amount')` for
  `PENDING`/`PARTIAL`/`OVERDUE`.
- `vendas_hoje` — count of `COMPLETED` sales today.

Rendered with `frontend/templates/frontend/reports.html`. Verified by
`test_report_best_selling`, `test_report_receivable_open`, and
`test_report_empty_dataset` (an empty aggregate returns `None`, which callers
coalesce to `0`).

### Known frontend limitation

The dashboard/reports numbers come from the database and are accurate. The
browser-side interactive layer has a known wiring defect that is **not** an
operational feature and is out of scope here: `static/js/main.js` calls
`initCarrinhos()` inside `DOMContentLoaded`, but no such function is defined, and
several templates call `quadrum.showToast`/`quadrum.copyToClipboard`, which the
exported `window.quadrum` object does not provide. These calls cannot be relied
upon. In addition, the POS template `frontend/templates/frontend/point_of_sale.html`
builds its checkout payload with Portuguese field names (`itens`, `produto_id`,
`forma_pagamento`, `cliente_id`), while `api_pos_finalize` reads the English
field names documented in the [API reference](api-reference.md). The bundled UI
therefore does not currently produce a payload the endpoint accepts. Fixing the
frontend is a separate engineering task and was not performed in this
documentation phase.
