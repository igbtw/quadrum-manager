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

**Entry point:** `POST /api/pos/calculate/` → `frontend.views.api_pos_calculate`
(URL name `frontend:api_pos_calculate`).

**Ordered processing steps:**

1. `@login_required` and `@require_http_methods(["POST"])` gate the request.
2. `json.loads(request.body)` parses the body; a JSON decoding failure returns
   `400 {"error": "Invalid JSON body"}`.
3. `items = data.get('items', [])` is read.
4. Validate the payload with `_validate_pos_items` (`frontend/views.py`):
   `items` must be an array of objects; each `product_id` and `quantity` must be
   a positive JSON integer (booleans, floats such as `2.0`/`2.5`, numeric
   strings, `null`, zero, and negatives are rejected; a missing `quantity` is
   rejected). Invalid input returns `400` before any product lookup.
5. For each validated item, the product is looked up with
   `Product.objects.get(pk=item['product_id'], active=True)`.
6. If the product does not exist (or is inactive), the loop returns
   `404 {"error": "Product <id> not found"}`.
7. Otherwise the running total is increased by
   `product.price * Decimal(quantity)`.
8. The view returns `200 {"total": "<decimal>"}` — the total is a **string**.

**Functions and files:** `api_pos_calculate` in `frontend/views.py`; reads
`Product` from `frontend/models.py`.

**Price handling:** the endpoint never reads a client-supplied price. It sums
`Product.price` from the database. Client prices sent alongside are ignored.

**Database writes and side effects:** none. The endpoint is read-only and does
not reserve or guarantee stock; it only reports an indicative total.

**Validation and error paths:**

- Invalid input → `400` with a controlled message: malformed JSON →
  `Invalid JSON body`; non-object body → `Invalid request body`; non-array
  `items` → `Invalid items`; non-object item → `Invalid item`; bad `product_id`
  → `Invalid product_id`; missing or bad `quantity` → `Invalid quantity`.
- Unknown/inactive product (valid positive id) → `404` with
  `Product <id> not found`.
- Unexpected server-side exception → logged via `logger.exception` and returned
  as `400 {"error": "Calculation error"}` with no exception text. (This path
  returns `400` in the current code; that status for an unexpected failure may
  merit a future API-contract review.)

**Tests:** `test_api_pos_calcular_real_product` and `test_api_pos_calcular_bad_id`
in `frontend/tests/test_regressions.py`; `test_invalid_product_id_in_api` in
`frontend/tests/test_auth_security.py`; and the `PosApiValidationTests` cases
(`test_calculate_valid_total`, `test_calculate_ignores_client_price`,
`test_calculate_rejects_invalid_quantities`,
`test_calculate_rejects_missing_quantity`,
`test_calculate_rejects_invalid_product_ids`,
`test_calculate_rejects_malformed_items`,
`test_calculate_missing_product_returns_404`,
`test_calculate_unexpected_error_hides_internal_details`,
`test_calculate_malformed_json_returns_controlled_error`).

## B. Sale finalization

**Entry point:** `POST /api/pos/finalize/` → `frontend.views.api_pos_finalize`
(URL name `frontend:api_pos_finalize`).

**Ordered processing steps (verified against `frontend/views.py`):**

1. `@login_required` and `@require_http_methods(["POST"])` gate the request.
2. Parse the body with `json.loads`. Read `items`, `customer_id`,
   `payment_method` (default `"CASH"`), and `idempotency_key` (coerced to string
   and stripped).
3. Reject an empty cart: `400 {"error": "Empty cart"}`.
4. Validate items with `_validate_pos_items`: every `product_id` and `quantity`
   must be a positive JSON integer (booleans, floats, strings, `null`, zero,
   negatives, and missing quantities rejected) → `400` with a controlled
   message.
5. Validate `payment_method` against the five declared codes (`CASH`, `DEBIT`,
   `CREDIT`, `PIX`, `ON_ACCOUNT`); unknown values, casing variants, and
   whitespace are rejected → `400 {"error": "Invalid payment method"}`.
6. Validate the idempotency key (non-empty, `<= 255` chars, matching
   `^[A-Za-z0-9_-]+$`): otherwise `400 {"error": "Invalid idempotency key"}`.
7. Compute the request fingerprint from the **validated** items and payment
   method (see [section C](#c-idempotency-and-retries)); the fingerprinted
   quantities are the values that will be persisted.
8. If `customer_id` is provided, resolve `Person.objects.get(pk=..., active=True)`;
   if not found, `404 {"error": "Customer not found"}`.
9. Open `transaction.atomic()` and look up an existing `Sale` by
   `idempotency_key`:
   - **Found, different owner** → `403 {"error": "Idempotency key not authorized"}`.
   - **Found, `COMPLETED`, fingerprint mismatch** → `409 {"error": "Key conflict: request data changed"}`.
   - **Found, `COMPLETED`, no fingerprint** → `409 {"error": "Key conflict: existing sale without verification fingerprint"}`.
   - **Found, `COMPLETED`, fingerprint match** → `200` replay with the existing
     `code` (no writes).
   - **Found, any other status** → `409 {"error": "Checkout attempt already in progress or incomplete"}`.
   - **Not found** → continue.
10. Create the `Sale` with `status='PENDING'`, `payment_method`, zero
    `subtotal`/`total`, the `idempotency_key`, and the `request_fingerprint`.
    `responsible` is the authenticated user.
11. Pass the validated items to `create_sale_items(sale, items, user=...)`: for
    each item, guard that `quantity` is a positive integer (service-level
    defense in depth), lock the product, use `Product.price` as `unit_price`,
    create the `SaleItem` (subtotal computed in `SaleItem.save()`), and call
    `reduce_stock()` (which decrements stock and writes a `SALE`
    `StockMovement`). Any client `unit_price` is discarded.
12. Sum the item subtotals into `sale.subtotal` and `sale.total` and save
    (`update_fields=['subtotal', 'total', 'request_fingerprint']`).
13. `finalize_sale(sale, user=...)`: lock the sale, return early if already
    `COMPLETED`, otherwise set `status='COMPLETED'`, `completed_at=now`,
    `responsible`, save, and — for `ON_ACCOUNT` sales with a customer — create an
    `AccountReceivable` via `get_or_create` (`person`, `original_amount=total`,
    `due_date=completed_at.date()`, `status='PENDING'`).
14. Return `200 {"success": true, "code": sale.code, "message": "Sale completed"}`.

**Database writes and side effects:** one `Sale`, one `SaleItem` per line,
`Product.stock_quantity` decrements, one `SALE` `StockMovement` per line, and
(conditionally) one `AccountReceivable`. No `Payment` is created by this flow.

**Transactional guarantee:** the view wraps steps 9–14 in a single
`transaction.atomic()`, so on failure all of those writes roll back together.
This is a confirmed guarantee of the code path, not an assumption.

**Error handling and rollback:**

- `IntegrityError` (typically a concurrent insert of the same idempotency key) is
  caught, the sale is re-read by key, and the same ownership/fingerprint/status
  responses are produced (`403`/`409`/replay `200`). If no matching record exists,
  the view logs the exception and returns
  `500 {"error": "Internal error finalizing sale"}`.
- Insufficient stock (`InsufficientStockError` raised by `reduce_stock()` from the
  locked mutation path) propagates out of the `transaction.atomic()` block and is
  mapped to `409 {"error": "Insufficient stock"}`. Because it leaves the atomic
  block first, every checkout write — `Sale`, `SaleItem`, `StockMovement`,
  conditional `AccountReceivable`, and the stock decrement — is rolled back; stock
  never goes negative. The response is a stable business-conflict message with no
  internal detail and is not logged as a server error.
- Any other exception is logged and returns the same generic `500` body with no
  internal detail.
- Stock is reduced cumulatively per line under the product row lock, so duplicate
  lines for one product that together exceed inventory fail and roll back rather
  than passing individual per-line checks.
- The calculation endpoint (flow A) does not reserve stock, so availability is
  only guaranteed at finalization.

**Idempotency/ownership/conflict details** are in
[section C](#c-idempotency-and-retries).

**Tests:** `test_api_pos_requires_login_and_ignores_client_price`,
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

- `items`: `sorted((product_id, quantity) ...)` built from the validated items —
  item order is irrelevant, values are already positive integers, and
  `unit_price` is excluded;
- `customer_id`: `int(customer_id)` or `None`;
- `payment_method`: the validated code.

The normalized dict is serialized with `json.dumps(..., sort_keys=True)` and
hashed with SHA-256. It is stored in `Sale.request_fingerprint`.

**Equivalent retry:** the same key with an equivalent payload (same items,
quantities, customer, and method) finds the existing `COMPLETED` sale with a
matching fingerprint and returns `200 {"success": true, "code": <code>,
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
| Invalid item, product id, or quantity | 400 | `Invalid items` / `Invalid item` / `Invalid product_id` / `Invalid quantity` |
| Invalid payment method | 400 | `Invalid payment method` |
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
not tested. Item and `payment_method` validation now happen before
fingerprinting, but that validation is verified only by `PosApiValidationTests`,
not under concurrency.

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
4. For `ON_ACCOUNT` sales, locks the associated receivable with
   `select_for_update()` **before** any payment check, so cancellation serializes
   with `register_payment()`/`Payment.save()` on the same row.
5. If a locked receivable already has payments, raises
   `ValueError('Cannot cancel: recorded payments exist on the
   receivable account.')`.
6. Sets `status='CANCELLED'` and saves.
7. If a receivable was locked, marks it `CANCELLED` (the record is never
   deleted).
8. For each item, locks the product, restores `stock_quantity += quantity`, and
   writes a `RETURN` `StockMovement`.

Lock order is sale → receivable → products. The payment path locks the receivable
only, so there is no lock cycle. If no receivable is associated (e.g. a non
`ON_ACCOUNT` sale, or an `ON_ACCOUNT` sale without a customer), cancellation
proceeds without a receivable lock and performs no payment check, preserving the
prior behavior.

**Tests:** `test_cancel_sale_idempotent_and_reversal`,
`test_cancel_rejected_if_payments_exist`,
`test_cancel_rejected_after_payment_leaves_no_partial_writes` in
`frontend/tests/test_regressions.py`;
`test_inventory_adjustment_and_history`, `test_cancel_idempotent_and_rejected_with_payments`,
`test_failed_inventory_does_not_partial_update` in
`frontend/tests/test_integration.py`.

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
   The `account_receivable` field queryset excludes records whose status is
   `CANCELLED`, so cancelling a receivable removes it from the selectable options
   and a POST of a cancelled key fails with Django's invalid-choice error.
2. On valid input, calls
   `register_payment(rc, amount, method=..., user=request.user, notes=...)`.
3. Success shows `Payment registered.`; failure shows `Please verify the payment.`.

The form restriction is a UI safeguard only. The pattern is enforced at three
other layers so a caller that bypasses the form is still blocked: the
`register_payment()` service guard, `Payment.clean()` (model `full_clean`), and the
ordinary `Payment.save()`/`objects.create()` write path.

**`register_payment(account_receivable, amount, method='CASH', user=None, notes='')`**
(`frontend/models.py`):

1. Opens `transaction.atomic()`.
2. Reloads and locks the receivable:
   `AccountReceivable.objects.select_for_update().get(pk=account_receivable.pk)`.
3. If the locked status is `CANCELLED`, raises
   `ValueError('Cannot register payment for a cancelled receivable.')` — before
   the balance check and before creating a `Payment`.
4. If `amount > rc.remaining_balance`, raises
   `ValueError('Payment exceeds remaining balance.')`.
5. Creates the `Payment` (which triggers `Payment.save()`'s cancelled-receivable
   guard and status recalculation).
6. Calls `rc.update_status()` and saves `status`.

**Model-save guard (defense in depth):** `Payment.save()` and `Payment.clean()`
reject a payment that is new or reassigned to a receivable whose status is
`CANCELLED`. `Payment.save()` locks the persisted receivable with
`select_for_update()`, checks its status, and performs the payment insert within
the same `transaction.atomic()` block, raising `ValidationError` before any write
if the receivable is cancelled. A direct
`Payment.objects.create(account_receivable=<cancelled>, ...)` therefore cannot
insert a row. Unrelated metadata edits to an existing payment remain allowed even
if its receivable later became `CANCELLED`. The checks run only for new rows or a
changed receivable association.

**Outstanding balance:** `remaining_balance` is `original_amount` minus the sum of
all payments, floored at zero. `amount_paid` aggregates payments with
`Sum('amount')`.

**Concurrency:** the receivable row is locked with `select_for_update()`, so
concurrent payments against the same receivable serialize on backends that
support row locking (PostgreSQL). `cancel_sale()` locks the same receivable row
before checking for payments and before marking it `CANCELLED`, so a payment and
a cancellation of the same receivable serialize: whichever commits first is
observed by the other (a committed payment blocks cancellation; a committed
cancellation blocks the later payment). Lock order is sale → receivable →
products; the payment path locks only the receivable, so there is no cycle. On
SQLite the lock is effectively ignored, so this ordering is **not** demonstrated
by the test suite (no PostgreSQL concurrency test is run). There is no
application-level lock or retry loop, and `bulk_create()`/raw SQL bypass these
guards.

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

- If `status == 'CANCELLED'`, it returns immediately and the status is left
  unchanged — cancellation is **terminal** in recalculation.
- Otherwise: `remaining_balance <= 0` → `PAID` (this check runs first, so a fully paid
  receivable is `PAID` even if past due).
- `due_date < today` and `remaining_balance > 0` → `OVERDUE`.
- `amount_paid > 0` (with a remaining balance, not past due) → `PARTIAL`.
- otherwise → `PENDING`.

A cancelled receivable may legitimately carry a positive `remaining_balance`
because its sale was cancelled; that balance must not reopen it as
`PENDING`/`PARTIAL`/`PAID`/`OVERDUE`. Since both `register_payment()` and
`Payment.save()` recalculate through `update_status()`, the guard protects both
paths. Verified by `test_update_status_preserves_cancelled_with_balance` and
`test_update_status_recalculates_non_cancelled`.

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
restored with `RETURN` movements. Once `CANCELLED`, the receivable is closed:
`register_payment()` refuses further payments (`ValueError`), `Payment.clean()`/
`Payment.save()` refuse new or reassigned payments (`ValidationError`), and
`update_status()` never reopens it. Verified by
`test_cancel_rejected_if_payments_exist` and
`test_cancel_idempotent_and_rejected_with_payments`.

## G. Dashboard and reports

### Dashboard (`frontend.views.dashboard`, public)

Aggregates over the current date (`timezone.now().date()`):

- `sales_today` — count of `COMPLETED` sales created today.
- `daily_revenue` — `Sum('total')` of `COMPLETED` sales today (defaults to `0.00`).
- `receivables_total` — `Sum('original_amount')` for receivables in
  `PENDING`/`PARTIAL`/`OVERDUE`. This uses the **original** amount, not the
  remaining balance (a simplification noted in a code comment).
- Low-stock count (active, `stock_quantity <= minimum_stock`, `> 0`) and
  out-of-stock count (active, `stock_quantity == 0`).
- Five most recent sales and five low-stock products.

Rendered with `frontend/templates/frontend/dashboard.html`. Verified in part by
`test_dashboard_sales_today` and `test_report_low_stock`.

### Reports (`frontend.views.reports`, protected)

- `period_sales` — `COMPLETED` sales with `created_at__date >= today - 7 days`.
- `period_sales_total` — `Sum('total')` over that period; `period_sales_count`
  — its count.
- `best_selling` — top 5 products by `Sum('quantity')` over `SaleItem` rows whose
  sale is `COMPLETED`, grouped by `product__name`.
- `low_stock_count` — active products with `stock_quantity <= minimum_stock`.
- `receivable_total` — `Sum('original_amount')` for
  `PENDING`/`PARTIAL`/`OVERDUE`.
- `sales_today` — count of `COMPLETED` sales today.

Rendered with `frontend/templates/frontend/reports.html`. Verified by
`test_report_best_selling`, `test_report_receivable_open`, and
`test_report_empty_dataset` (an empty aggregate returns `None`, which callers
coalesce to `0`).

### Frontend wiring

The dashboard/reports numbers come from the database and are accurate.
`static/js/main.js` defines and exports the helpers used by the templates,
including `showToast`, `copyToClipboard`, and `showNotification`, and initializes
filters and notifications on `DOMContentLoaded`. The POS template
`frontend/templates/frontend/point_of_sale.html` sends the English payload
(`items`, `customer_id`, `payment_method`, `idempotency_key`) documented in the
[API reference](api-reference.md). One pre-existing limitation remains: the
template queries `#selected-customer`, which it does not render, so
`customer_id` is always `null` and on-account sales created from this UI have no
customer or receivable.
