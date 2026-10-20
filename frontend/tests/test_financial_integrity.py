"""Financial integrity, payment safety and billing audit coverage.

These tests exercise the authoritative paths (service, ORM, form, view,
database constraint, concurrency, diagnostics) and assert persisted database
state, not only user-facing messages.
"""
import threading
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from frontend.forms import PaymentForm
from frontend.models import (
    AccountReceivable, Category, Payment, PaymentConflictError, Person,
    Product, Sale, register_payment,
)


class FinancialTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('finance-user', password='test-pass-123')
        self.person = Person.objects.create(name='Ana Lima', person_type='STUDENT')
        self.category = Category.objects.create(name='Bebidas')
        self.product = Product.objects.create(
            name='Suco', code='SUCO-FIN', category=self.category,
            price=Decimal('10.00'), stock_quantity=50,
        )

    def make_sale(self, total=Decimal('100.00'), responsible=None):
        return Sale.objects.create(
            customer=self.person,
            responsible=self.user if responsible is None else responsible,
            status='COMPLETED', payment_method='ON_ACCOUNT', total=total,
        )

    def make_receivable(self, original=Decimal('100.00'), status='PENDING', sale=None):
        return AccountReceivable.objects.create(
            person=self.person,
            sale=self.make_sale(total=original) if sale is None else sale,
            original_amount=original,
            due_date='2030-01-01',
            status=status,
        )


class PaymentEligibilityServiceTests(FinancialTestBase):
    def test_settled_receivable_rejects_new_payment_with_explicit_message(self):
        rc = self.make_receivable(original=Decimal('40.00'))
        register_payment(rc, Decimal('40.00'), user=self.user)
        with self.assertRaisesMessage(ValueError, 'This account is already settled.'):
            register_payment(rc, Decimal('10.00'), user=self.user)
        self.assertEqual(Payment.objects.filter(account_receivable=rc).count(), 1)

    def test_stale_paid_with_positive_balance_still_accepts_payment(self):
        rc = self.make_receivable(original=Decimal('100.00'))
        register_payment(rc, Decimal('40.00'), user=self.user)
        AccountReceivable.objects.filter(pk=rc.pk).update(status='PAID')
        rc.refresh_from_db()
        self.assertEqual(rc.status, 'PAID')
        self.assertEqual(rc.remaining_balance, Decimal('60.00'))
        payment = register_payment(rc, Decimal('60.00'), user=self.user)
        self.assertIsNotNone(payment.pk)
        rc.refresh_from_db()
        self.assertEqual(rc.status, 'PAID')
        self.assertEqual(rc.remaining_balance, Decimal('0.00'))
        self.assertEqual(Payment.objects.filter(account_receivable=rc).count(), 2)

    def test_cancelled_receivable_rejects_payment_even_with_balance(self):
        rc = self.make_receivable(original=Decimal('50.00'), status='CANCELLED')
        with self.assertRaisesMessage(
            ValueError, 'Cannot register payment for a cancelled receivable.',
        ):
            register_payment(rc, Decimal('10.00'), user=self.user)
        self.assertFalse(Payment.objects.filter(account_receivable=rc).exists())

    def test_overpayment_is_rejected_and_ledger_unchanged(self):
        rc = self.make_receivable(original=Decimal('30.00'))
        with self.assertRaisesMessage(ValueError, 'Payment exceeds remaining balance.'):
            register_payment(rc, Decimal('30.01'), user=self.user)
        self.assertFalse(Payment.objects.filter(account_receivable=rc).exists())
        self.assertEqual(
            AccountReceivable.objects.get(pk=rc.pk).remaining_balance,
            Decimal('30.00'),
        )

    def test_amount_below_minimum_is_rejected(self):
        rc = self.make_receivable()
        with self.assertRaisesMessage(ValueError, 'Payment amount must be at least R$ 0.01.'):
            register_payment(rc, Decimal('0.00'), user=self.user)
        self.assertFalse(Payment.objects.filter(account_receivable=rc).exists())

    def test_sub_cent_amount_is_rejected(self):
        rc = self.make_receivable()
        with self.assertRaisesMessage(ValueError, 'at most two decimal places'):
            register_payment(rc, Decimal('10.001'), user=self.user)
        self.assertFalse(Payment.objects.filter(account_receivable=rc).exists())

    def test_repeated_small_payments_leave_no_float_residue(self):
        rc = self.make_receivable(original=Decimal('0.30'))
        register_payment(rc, Decimal('0.10'), user=self.user)
        register_payment(rc, Decimal('0.20'), user=self.user)
        rc.refresh_from_db()
        self.assertEqual(rc.amount_paid, Decimal('0.30'))
        self.assertEqual(rc.remaining_balance, Decimal('0.00'))
        self.assertEqual(rc.status, 'PAID')
        with self.assertRaises(ValueError):
            register_payment(rc, Decimal('0.01'), user=self.user)

    def test_thirds_of_eighty_thirty_settle_exactly(self):
        rc = self.make_receivable(original=Decimal('80.30'))
        for amount in (Decimal('26.77'), Decimal('26.76'), Decimal('26.77')):
            register_payment(rc, amount, user=self.user)
        rc.refresh_from_db()
        self.assertEqual(rc.amount_paid, Decimal('80.30'))
        self.assertEqual(rc.remaining_balance, Decimal('0.00'))
        self.assertEqual(rc.status, 'PAID')

    def test_status_transitions_use_exact_balances(self):
        rc = self.make_receivable(original=Decimal('10.00'))
        register_payment(rc, Decimal('5.00'), user=self.user)
        self.assertEqual(AccountReceivable.objects.get(pk=rc.pk).status, 'PARTIAL')
        register_payment(rc, Decimal('5.00'), user=self.user)
        self.assertEqual(AccountReceivable.objects.get(pk=rc.pk).status, 'PAID')


class PaymentIdempotencyTests(FinancialTestBase):
    def test_replay_with_same_key_and_params_returns_same_payment(self):
        rc = self.make_receivable()
        first = register_payment(
            rc, Decimal('25.00'), user=self.user, idempotency_key='replay-key-1',
        )
        second = register_payment(
            rc, Decimal('25.00'), user=self.user, idempotency_key='replay-key-1',
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Payment.objects.filter(account_receivable=rc).count(), 1)
        self.assertEqual(
            AccountReceivable.objects.get(pk=rc.pk).remaining_balance,
            Decimal('75.00'),
        )

    def test_replay_after_settlement_resolves_to_original_payment(self):
        rc = self.make_receivable(original=Decimal('20.00'))
        first = register_payment(
            rc, Decimal('20.00'), user=self.user, idempotency_key='settle-key-1',
        )
        self.assertEqual(AccountReceivable.objects.get(pk=rc.pk).status, 'PAID')
        second = register_payment(
            rc, Decimal('20.00'), user=self.user, idempotency_key='settle-key-1',
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Payment.objects.filter(account_receivable=rc).count(), 1)

    def test_same_key_different_amount_is_rejected_without_mutation(self):
        rc = self.make_receivable()
        register_payment(
            rc, Decimal('25.00'), user=self.user, idempotency_key='conflict-key-1',
        )
        with self.assertRaises(PaymentConflictError):
            register_payment(
                rc, Decimal('30.00'), user=self.user, idempotency_key='conflict-key-1',
            )
        self.assertEqual(Payment.objects.filter(account_receivable=rc).count(), 1)
        self.assertEqual(
            Payment.objects.get(idempotency_key='conflict-key-1').amount,
            Decimal('25.00'),
        )

    def test_same_key_different_receivable_is_rejected(self):
        first_rc = self.make_receivable(original=Decimal('40.00'))
        second_rc = self.make_receivable(original=Decimal('40.00'))
        register_payment(
            first_rc, Decimal('10.00'), user=self.user, idempotency_key='cross-key-1',
        )
        with self.assertRaises(PaymentConflictError):
            register_payment(
                second_rc, Decimal('10.00'), user=self.user, idempotency_key='cross-key-1',
            )
        self.assertFalse(Payment.objects.filter(account_receivable=second_rc).exists())

    def test_same_key_different_method_is_rejected(self):
        rc = self.make_receivable()
        register_payment(
            rc, Decimal('10.00'), method='CASH', user=self.user,
            idempotency_key='method-key-1',
        )
        with self.assertRaises(PaymentConflictError):
            register_payment(
                rc, Decimal('10.00'), method='PIX', user=self.user,
                idempotency_key='method-key-1',
            )
        self.assertEqual(Payment.objects.filter(account_receivable=rc).count(), 1)

    def test_payment_without_key_still_works(self):
        rc = self.make_receivable(original=Decimal('20.00'))
        payment = register_payment(rc, Decimal('10.00'), user=self.user)
        self.assertIsNone(payment.idempotency_key)
        self.assertEqual(Payment.objects.filter(account_receivable=rc).count(), 1)

    def test_database_enforces_unique_idempotency_key(self):
        rc = self.make_receivable()
        Payment.objects.create(
            account_receivable=rc, amount=Decimal('5.00'), method='CASH',
            idempotency_key='unique-db-key',
        )
        with self.assertRaises(IntegrityError):
            Payment.objects.create(
                account_receivable=rc, amount=Decimal('5.00'), method='PIX',
                idempotency_key='unique-db-key',
            )


class PaymentOrmGuardTests(FinancialTestBase):
    def test_direct_create_above_balance_is_rejected(self):
        rc = self.make_receivable(original=Decimal('30.00'))
        with self.assertRaisesMessage(
            ValidationError, 'Payment cannot exceed remaining balance.',
        ):
            Payment.objects.create(
                account_receivable=rc, amount=Decimal('30.01'), method='CASH',
            )
        self.assertFalse(Payment.objects.filter(account_receivable=rc).exists())

    def test_direct_create_on_settled_receivable_is_rejected(self):
        rc = self.make_receivable(original=Decimal('20.00'))
        register_payment(rc, Decimal('20.00'), user=self.user)
        with self.assertRaisesMessage(ValidationError, 'This account is already settled.'):
            Payment.objects.create(
                account_receivable=rc, amount=Decimal('1.00'), method='CASH',
            )
        self.assertEqual(Payment.objects.filter(account_receivable=rc).count(), 1)

    def test_direct_create_below_minimum_is_rejected(self):
        rc = self.make_receivable()
        with self.assertRaises(ValidationError):
            Payment.objects.create(
                account_receivable=rc, amount=Decimal('0.001'), method='CASH',
            )
        self.assertFalse(Payment.objects.filter(account_receivable=rc).exists())

    def test_reassignment_to_insufficient_receivable_is_rejected(self):
        source = self.make_receivable(original=Decimal('100.00'))
        target = self.make_receivable(original=Decimal('30.00'))
        payment = Payment.objects.create(
            account_receivable=source, amount=Decimal('40.00'), method='CASH',
        )
        payment.account_receivable = target
        with self.assertRaises(ValidationError):
            payment.save()
        stored = Payment.objects.get(pk=payment.pk)
        self.assertEqual(stored.account_receivable_id, source.pk)
        self.assertEqual(
            AccountReceivable.objects.get(pk=source.pk).remaining_balance,
            Decimal('60.00'),
        )

    def test_edit_above_available_balance_is_rejected(self):
        rc = self.make_receivable(original=Decimal('100.00'))
        payment = Payment.objects.create(
            account_receivable=rc, amount=Decimal('40.00'), method='CASH',
        )
        payment.amount = Decimal('101.00')
        with self.assertRaises(ValidationError):
            payment.save()
        self.assertEqual(Payment.objects.get(pk=payment.pk).amount, Decimal('40.00'))
        self.assertEqual(
            AccountReceivable.objects.get(pk=rc.pk).remaining_balance,
            Decimal('60.00'),
        )

    def test_edit_downwards_credits_own_amount_and_updates_status(self):
        rc = self.make_receivable(original=Decimal('80.30'))
        register_payment(rc, Decimal('80.30'), user=self.user)
        self.assertEqual(AccountReceivable.objects.get(pk=rc.pk).status, 'PAID')
        payment = Payment.objects.get(account_receivable=rc)
        payment.amount = Decimal('60.00')
        payment.save()
        rc.refresh_from_db()
        self.assertEqual(rc.status, 'PARTIAL')
        self.assertEqual(rc.amount_paid, Decimal('60.00'))
        self.assertEqual(rc.remaining_balance, Decimal('20.30'))


class PaymentFormEligibilityTests(FinancialTestBase):
    def test_choices_only_include_accounts_with_positive_balance(self):
        open_rc = self.make_receivable(original=Decimal('40.00'))
        settled_rc = self.make_receivable(original=Decimal('25.00'))
        register_payment(settled_rc, Decimal('25.00'), user=self.user)
        form = PaymentForm(user=self.user)
        choice_values = {
            str(value)
            for value, _ in form.fields['account_receivable'].widget.choices
            if value
        }
        self.assertIn(str(open_rc.pk), choice_values)
        self.assertNotIn(str(settled_rc.pk), choice_values)
        queryset_values = {
            str(pk)
            for pk in form.fields['account_receivable'].queryset.values_list('pk', flat=True)
        }
        self.assertIn(str(settled_rc.pk), queryset_values)

    def test_stale_paid_with_balance_still_offered_and_accepted(self):
        rc = self.make_receivable(original=Decimal('100.00'))
        register_payment(rc, Decimal('40.00'), user=self.user)
        AccountReceivable.objects.filter(pk=rc.pk).update(status='PAID')
        form = PaymentForm(user=self.user)
        choice_values = {
            str(value)
            for value, _ in form.fields['account_receivable'].widget.choices
            if value
        }
        self.assertIn(str(rc.pk), choice_values)
        bound = PaymentForm(
            data={
                'account_receivable': rc.pk, 'amount': '60.00',
                'method': 'CASH', 'notes': '',
            },
            user=self.user,
        )
        self.assertTrue(bound.is_valid(), bound.errors)
        self.assertEqual(bound.cleaned_data['amount'], Decimal('60.00'))

    def test_posted_settled_account_has_explicit_error(self):
        rc = self.make_receivable(original=Decimal('25.00'))
        register_payment(rc, Decimal('25.00'), user=self.user)
        form = PaymentForm(
            data={
                'account_receivable': rc.pk, 'amount': '5.00',
                'method': 'CASH', 'notes': '',
            },
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn(
            'This account is already settled.',
            form.errors['account_receivable'],
        )

    def test_posted_over_balance_is_rejected(self):
        rc = self.make_receivable(original=Decimal('30.00'))
        form = PaymentForm(
            data={
                'account_receivable': rc.pk, 'amount': '30.01',
                'method': 'CASH', 'notes': '',
            },
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('Payment exceeds remaining balance.', form.errors['amount'])

    def test_three_decimal_amount_is_rejected(self):
        rc = self.make_receivable()
        form = PaymentForm(
            data={
                'account_receivable': rc.pk, 'amount': '10.001',
                'method': 'CASH', 'notes': '',
            },
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertTrue(
            any('decimal places' in message for message in form.errors['amount']),
        )

    def test_missing_key_is_generated_server_side(self):
        rc = self.make_receivable()
        form = PaymentForm(
            data={
                'account_receivable': rc.pk, 'amount': '10.00',
                'method': 'CASH', 'notes': '',
            },
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.cleaned_data['idempotency_key'])


class FinanceViewPaymentTests(FinancialTestBase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.user)
        self.rc = self.make_receivable(original=Decimal('50.00'))

    def post_payment(self, amount='20.00', key='view-key-1', follow=True):
        return self.client.post(
            reverse('frontend:finance'),
            {
                'account_receivable': self.rc.pk,
                'amount': amount,
                'method': 'CASH',
                'notes': '',
                'idempotency_key': key,
            },
            follow=follow,
        )

    def test_payment_post_persists_and_updates_status(self):
        response = self.post_payment()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Payment.objects.filter(account_receivable=self.rc).count(), 1)
        rc = AccountReceivable.objects.get(pk=self.rc.pk)
        self.assertEqual(rc.status, 'PARTIAL')
        self.assertEqual(rc.remaining_balance, Decimal('30.00'))
        self.assertContains(response, 'Payment registered.')

    def test_replayed_post_does_not_charge_twice(self):
        self.post_payment(key='view-replay-1')
        self.post_payment(key='view-replay-1')
        self.assertEqual(Payment.objects.filter(account_receivable=self.rc).count(), 1)
        self.assertEqual(
            AccountReceivable.objects.get(pk=self.rc.pk).remaining_balance,
            Decimal('30.00'),
        )

    def test_same_key_different_amount_shows_error_and_persists_nothing(self):
        self.post_payment(amount='20.00', key='view-conflict-1')
        response = self.post_payment(amount='25.00', key='view-conflict-1')
        self.assertContains(
            response,
            'This payment submission key was already used for a different request.',
        )
        self.assertEqual(Payment.objects.filter(account_receivable=self.rc).count(), 1)
        self.assertEqual(
            AccountReceivable.objects.get(pk=self.rc.pk).remaining_balance,
            Decimal('30.00'),
        )

    def test_posted_settled_account_is_rejected_end_to_end(self):
        register_payment(self.rc, Decimal('50.00'), user=self.user)
        response = self.post_payment(amount='5.00', key='view-settled-1')
        self.assertEqual(Payment.objects.filter(account_receivable=self.rc).count(), 1)
        self.assertIn(
            'This account is already settled.',
            response.context['form'].errors['account_receivable'],
        )

    def test_invalid_field_errors_are_rendered_and_linked(self):
        response = self.post_payment(amount='0.00', follow=False)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, 'id="id_amount_error"')
        self.assertContains(response, 'Minimum value is 0.01.')

    def test_hidden_idempotency_field_is_rendered(self):
        response = self.client.get(reverse('frontend:finance'))
        self.assertContains(response, 'name="idempotency_key"')


class ReceivableConstraintTests(FinancialTestBase):
    def test_zero_amount_receivable_violates_database_constraint(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            AccountReceivable.objects.create(
                person=self.person, original_amount=Decimal('0.00'),
                due_date='2030-01-01', status='PENDING',
            )

    def test_update_below_minimum_violates_database_constraint(self):
        rc = self.make_receivable()
        with self.assertRaises(IntegrityError), transaction.atomic():
            AccountReceivable.objects.filter(pk=rc.pk).update(
                original_amount=Decimal('0.001'),
            )
        self.assertEqual(
            AccountReceivable.objects.get(pk=rc.pk).original_amount,
            Decimal('100.00'),
        )


class ConcurrentPaymentTests(TransactionTestCase):
    """Real threads against the actual database engine.

    SQLite turns ``select_for_update()`` into a no-op, so ``register_payment``
    relies on a write-first lock plus bounded retries instead. Exactly one of
    two simultaneous full-balance payments may win; the loser must fail with a
    domain error, never a leaked lock error, and the ledger must not overpay.
    """

    def setUp(self):
        self.user = User.objects.create_user('thread-user', password='test-pass-123')
        self.person = Person.objects.create(name='Concurrent Cliente', person_type='STUDENT')
        self.rc = AccountReceivable.objects.create(
            person=self.person, original_amount=Decimal('100.00'),
            due_date='2030-01-01', status='PENDING',
        )

    def test_simultaneous_full_balance_payments_do_not_overpay(self):
        results = []
        barrier = threading.Barrier(2)

        def worker():
            try:
                barrier.wait(timeout=10)
                payment = register_payment(
                    self.rc, Decimal('100.00'), user=self.user,
                )
                results.append(('ok', payment.pk))
            except Exception as exc:  # noqa: BLE001 - asserted below
                results.append((type(exc).__name__, str(exc)))
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertEqual(len(results), 2)
        payments = Payment.objects.filter(account_receivable=self.rc)
        self.assertEqual(payments.count(), 1)
        self.assertEqual(
            AccountReceivable.objects.get(pk=self.rc.pk).remaining_balance,
            Decimal('0.00'),
        )
        successes = [result for result in results if result[0] == 'ok']
        failures = [result for result in results if result[0] != 'ok']
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)
        self.assertIn(failures[0][0], ('ValueError', 'PaymentConflictError'))
        self.assertNotIn('locked', failures[0][1].lower())
        self.assertEqual(successes[0][1], payments.get().pk)

    def test_simultaneous_partial_payments_never_exceed_balance(self):
        results = []
        barrier = threading.Barrier(2)

        def worker():
            try:
                barrier.wait(timeout=10)
                payment = register_payment(
                    self.rc, Decimal('60.00'), user=self.user,
                )
                results.append(('ok', payment.pk))
            except Exception as exc:  # noqa: BLE001 - asserted below
                results.append((type(exc).__name__, str(exc)))
            finally:
                connection.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertEqual(len(results), 2)
        stored = AccountReceivable.objects.get(pk=self.rc.pk)
        payments = Payment.objects.filter(account_receivable=self.rc)
        self.assertLessEqual(payments.count(), 1)
        self.assertLessEqual(
            sum((p.amount for p in payments), Decimal('0.00')),
            stored.original_amount,
        )
        if payments.count() == 1:
            self.assertEqual(stored.remaining_balance, Decimal('40.00'))
        for failure in (r for r in results if r[0] != 'ok'):
            self.assertNotIn('locked', failure[1].lower())


class ZeroAmountOnAccountTests(FinancialTestBase):
    def test_zero_total_on_account_sale_creates_no_degenerate_receivable(self):
        from frontend.services import finalize_sale

        sale = Sale.objects.create(
            customer=self.person, responsible=self.user, status='PENDING',
            payment_method='ON_ACCOUNT', total=Decimal('0.00'),
        )
        finalize_sale(sale, user=self.user)
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'COMPLETED')
        self.assertFalse(AccountReceivable.objects.filter(sale=sale).exists())

    def test_positive_total_on_account_sale_still_creates_receivable(self):
        from frontend.services import finalize_sale

        sale = Sale.objects.create(
            customer=self.person, responsible=self.user, status='PENDING',
            payment_method='ON_ACCOUNT', total=Decimal('12.50'),
        )
        finalize_sale(sale, user=self.user)
        receivable = AccountReceivable.objects.get(sale=sale)
        self.assertEqual(receivable.original_amount, Decimal('12.50'))
        self.assertEqual(receivable.status, 'PENDING')


class FinancialAuditCommandTests(FinancialTestBase):
    def run_audit(self):
        output = StringIO()
        call_command('audit_financials', stdout=output)
        return output.getvalue()

    def test_clean_ledger_reports_success_and_does_not_write(self):
        rc = self.make_receivable(original=Decimal('60.00'))
        register_payment(rc, Decimal('60.00'), user=self.user)
        before = list(
            AccountReceivable.objects.values_list('pk', 'status', 'original_amount'),
        )
        output = self.run_audit()
        self.assertIn('No financial integrity issues detected', output)
        after = list(
            AccountReceivable.objects.values_list('pk', 'status', 'original_amount'),
        )
        self.assertEqual(before, after)
        self.assertEqual(Payment.objects.count(), 1)

    def test_stale_paid_receivable_is_reported_and_left_untouched(self):
        rc = self.make_receivable(original=Decimal('100.00'))
        register_payment(rc, Decimal('40.00'), user=self.user)
        AccountReceivable.objects.filter(pk=rc.pk).update(status='PAID')
        output = self.run_audit()
        self.assertIn('status=PAID but R$ 60.00 outstanding', output)
        stored = AccountReceivable.objects.get(pk=rc.pk)
        self.assertEqual(stored.status, 'PAID')
        self.assertEqual(stored.remaining_balance, Decimal('60.00'))

    def test_overpayment_from_legacy_data_is_reported(self):
        rc = self.make_receivable(original=Decimal('50.00'))
        Payment.objects.bulk_create([
            Payment(
                account_receivable=rc, amount=Decimal('70.00'), method='CASH',
                notes='legacy import',
            ),
        ])
        output = self.run_audit()
        self.assertIn('paid beyond their original amount', output)
        self.assertIn('paid=R$ 70.00', output)

    def test_cancelled_with_payments_is_reported(self):
        rc = self.make_receivable(original=Decimal('40.00'), status='CANCELLED')
        Payment.objects.bulk_create([
            Payment(account_receivable=rc, amount=Decimal('10.00'), method='CASH'),
        ])
        output = self.run_audit()
        self.assertIn('cancelled but has 1 payment(s)', output)
        self.assertEqual(
            AccountReceivable.objects.get(pk=rc.pk).status, 'CANCELLED',
        )

    def test_sale_mismatch_is_reported(self):
        sale = self.make_sale(total=Decimal('75.00'))
        rc = self.make_receivable(original=Decimal('40.00'), sale=sale)
        output = self.run_audit()
        self.assertIn('differs from their sale total', output)
        self.assertIn(f'AR #{rc.pk}', output)

    def test_duplicate_keys_are_reported_when_present(self):
        output = self.run_audit()
        self.assertIn('Duplicate payment idempotency keys:', output)
        self.assertIn('none', output)

