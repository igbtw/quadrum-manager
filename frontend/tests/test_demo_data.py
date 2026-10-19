"""Tests for the reversible demo dataset commands.

Manifests always live in a throwaway temporary directory (see ``setUp``), so
tests can never read, overwrite, or delete the real development manifest.
"""
import json
import shutil
import tempfile
import uuid
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from frontend import demo_data
from frontend.demo_data import DEMO_PASSWORD, DEMO_USER_PREFIX
from frontend.models import (
    AccountReceivable,
    Category,
    Payment,
    Person,
    Product,
    Sale,
    SaleItem,
    StockMovement,
)

DEMO_USER_ONE = 'demo_ana.souza'


class DemoDataTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tmpdir = tempfile.mkdtemp(prefix='quadrum-demo-tests-')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmpdir, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.manifest_path = Path(self._tmpdir) / f'manifest-{uuid.uuid4().hex}.json'
        override = override_settings(
            ALLOW_DEMO_DATA_COMMANDS=True,
            DEMO_DATA_MANIFEST_PATH=str(self.manifest_path),
        )
        override.enable()
        self.addCleanup(override.disable)
        self.root = User.objects.create_user(
            username='root', password='root-test-pass',
            is_staff=True, is_superuser=True,
        )
        self.root_snapshot = (
            self.root.pk, self.root.password,
            self.root.is_staff, self.root.is_superuser, self.root.is_active,
        )
        self.today = timezone.localdate()

    def seed(self):
        out = StringIO()
        call_command('seed_demo_data', stdout=out)
        return out.getvalue()

    def clear(self):
        out = StringIO()
        call_command('clear_demo_data', stdout=out)
        return out.getvalue()

    def dashboard_stats(self, username=DEMO_USER_ONE, password=DEMO_PASSWORD):
        client = Client()
        self.assertTrue(client.login(username=username, password=password))
        response = client.get(reverse('frontend:dashboard'))
        self.assertEqual(response.status_code, 200)
        return response.content.decode(), response.context['stats']

    def assert_root_unchanged(self):
        self.root.refresh_from_db()
        self.assertEqual(
            (self.root.pk, self.root.password, self.root.is_staff,
             self.root.is_superuser, self.root.is_active),
            self.root_snapshot,
        )


class SeedDemoDataTests(DemoDataTestCase):
    def test_seed_creates_expected_dataset(self):
        self.seed()
        self.assertEqual(User.objects.filter(username__startswith=DEMO_USER_PREFIX).count(), 6)
        self.assertEqual(Category.objects.count(), 8)
        self.assertEqual(Product.objects.count(), 42)
        self.assertEqual(Person.objects.count(), 24)
        self.assertEqual(Sale.objects.count(), 80)
        self.assertEqual(Sale.objects.filter(status='COMPLETED').count(), 72)
        self.assertEqual(Sale.objects.filter(status='PENDING').count(), 4)
        self.assertEqual(Sale.objects.filter(status='CANCELLED').count(), 4)
        self.assertEqual(AccountReceivable.objects.count(), 10)
        self.assertGreaterEqual(Payment.objects.count(), 6)
        self.assertEqual(Product.objects.filter(active=False).count(), 3)
        self.assertEqual(Product.objects.filter(code__in=['PDQ-01', 'COX-01', 'REF-01', 'SUCO-01', 'DOC-01'], stock_quantity__gt=0).count(), 5)
        self.assertEqual(Product.objects.filter(code__in=['AGU-01', 'CAN-01'], stock_quantity=0).count(), 2)
        for user in User.objects.filter(username__startswith=DEMO_USER_PREFIX):
            self.assertTrue(user.is_active)
            self.assertFalse(user.is_staff)
            self.assertFalse(user.is_superuser)
            self.assertTrue(user.email.endswith('@example.test'))
        manifest = json.loads(self.manifest_path.read_text(encoding='utf-8'))
        self.assertEqual(manifest['tool'], 'seed_demo_data')
        self.assertEqual(manifest['counts']['sales_total'], 80)
        self.assertEqual(manifest['counts']['payments'], Payment.objects.count())
        self.assert_root_unchanged()

    def test_sale_math_and_stock_movements_are_consistent(self):
        self.seed()
        for sale in Sale.objects.filter(status='COMPLETED'):
            self.assertEqual(sale.total, sale.subtotal)
            items = list(sale.items.all())
            self.assertTrue(items)
            item_total = sum(item.subtotal for item in items)
            self.assertEqual(sale.total, item_total)
            for item in items:
                self.assertEqual(item.subtotal, item.unit_price * item.quantity)
                self.assertEqual(item.unit_price, item.product.price)
            movements = list(StockMovement.objects.filter(sale=sale))
            self.assertTrue(all(m.movement_type == 'SALE' for m in movements))
            self.assertEqual(sum(m.quantity for m in movements), -sum(i.quantity for i in items))
            self.assertIsNotNone(sale.completed_at)
        for sale in Sale.objects.filter(status='CANCELLED'):
            items = list(sale.items.all())
            movements = list(StockMovement.objects.filter(sale=sale))
            sale_moves = [m for m in movements if m.movement_type == 'SALE']
            return_moves = [m for m in movements if m.movement_type == 'RETURN']
            self.assertEqual(sum(m.quantity for m in sale_moves), -sum(i.quantity for i in items))
            self.assertEqual(sum(m.quantity for m in return_moves), sum(i.quantity for i in items))
        for sale in Sale.objects.filter(status='PENDING'):
            self.assertEqual(sale.total, Decimal('0.00'))
            self.assertEqual(sale.items.count(), 0)
            self.assertEqual(StockMovement.objects.filter(sale=sale).count(), 0)

    def test_inventory_ledger_matches_final_stock(self):
        self.seed()
        for product in Product.objects.all():
            movements = list(
                StockMovement.objects.filter(product=product).order_by('created_at', 'pk'),
            )
            balance = 0
            for movement in movements:
                balance += movement.quantity
                self.assertGreaterEqual(balance, 0, f'negative ledger for {product.code}')
            self.assertEqual(balance, product.stock_quantity)
            self.assertEqual(sum(m.quantity for m in movements), product.stock_quantity)
            if product.stock_quantity > 0 or product.sale_items.exists():
                entries = [m for m in movements if m.movement_type == 'ENTRY']
                self.assertEqual(len(entries), 1)
                self.assertGreater(entries[0].quantity, 0)

    def test_receivables_and_payments_are_coherent(self):
        self.seed()
        receivables = list(AccountReceivable.objects.select_related('sale'))
        self.assertEqual(len(receivables), 10)
        by_status = {}
        for receivable in receivables:
            by_status[receivable.status] = by_status.get(receivable.status, 0) + 1
            self.assertEqual(receivable.sale.payment_method, 'ON_ACCOUNT')
            self.assertIsNotNone(receivable.sale.customer)
            self.assertEqual(receivable.original_amount, receivable.sale.total)
            paid = receivable.amount_paid
            if receivable.status == 'PAID':
                self.assertEqual(paid, receivable.original_amount)
            elif receivable.status == 'PARTIAL':
                self.assertGreater(paid, Decimal('0.00'))
                self.assertLess(paid, receivable.original_amount)
            elif receivable.status == 'PENDING':
                self.assertEqual(paid, Decimal('0.00'))
                self.assertGreaterEqual(receivable.due_date, self.today)
            elif receivable.status == 'OVERDUE':
                self.assertEqual(paid, Decimal('0.00'))
                self.assertLess(receivable.due_date, self.today)
            else:
                self.fail(f'unexpected receivable status {receivable.status}')
        self.assertEqual(by_status, {'PAID': 3, 'PARTIAL': 3, 'PENDING': 2, 'OVERDUE': 2})
        for payment in Payment.objects.select_related('account_receivable'):
            self.assertGreater(payment.amount, Decimal('0.00'))
            self.assertLessEqual(payment.amount, payment.account_receivable.original_amount)

    def test_today_and_yesterday_have_activity(self):
        self.seed()
        yesterday = self.today - timezone.timedelta(days=1)
        self.assertEqual(
            Sale.objects.filter(status='COMPLETED', created_at__date=self.today).count(), 4,
        )
        self.assertEqual(
            Sale.objects.filter(status='COMPLETED', created_at__date=yesterday).count(), 2,
        )

    def test_dashboard_reflects_seeded_data(self):
        self.seed()
        html, stats = self.dashboard_stats(username='root', password='root-test-pass')
        self.assertEqual(stats['sales_today'], 4)
        self.assertEqual(stats['sales_delta']['value'], '+100%')
        self.assertEqual(stats['sales_delta']['class'], 'kpi-delta-up')
        self.assertGreater(stats['daily_revenue'], Decimal('0.00'))
        self.assertGreater(stats['receivables_open_count'], 0)
        self.assertEqual(stats['receivables_open_count'], 7)
        self.assertEqual(stats['low_stock_count'], 7)
        self.assertEqual(stats['low_inventory_meta'], {'text': 'needs attention', 'warn': True})
        self.assertEqual(len(stats['sales_chart']['units']), 7)
        self.assertGreater(stats['sales_chart']['units'][-1], 0)
        self.assertIn('needs attention', html)

    def test_duplicate_seed_is_refused(self):
        self.seed()
        with self.assertRaises(CommandError) as caught:
            self.seed()
        self.assertIn('clear_demo_data', str(caught.exception))
        self.assertEqual(Sale.objects.count(), 80)
        self.assertEqual(User.objects.filter(username__startswith=DEMO_USER_PREFIX).count(), 6)

    def test_failure_rolls_back_without_manifest(self):
        with mock.patch.object(demo_data, '_create_sales', side_effect=RuntimeError('boom')):
            with self.assertRaises(CommandError):
                self.seed()
        self.assertFalse(self.manifest_path.exists())
        self.assertEqual(User.objects.filter(username__startswith=DEMO_USER_PREFIX).count(), 0)
        self.assertEqual(Category.objects.count(), 0)
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(Sale.objects.count(), 0)

    def test_manifest_write_failure_removes_manifest_and_rolls_back(self):
        original_write = demo_data.write_manifest_atomic

        def exploding_write(data):
            original_write(data)
            raise RuntimeError('commit failed')

        with mock.patch.object(demo_data, 'write_manifest_atomic', side_effect=exploding_write):
            with self.assertRaises(CommandError):
                self.seed()
        self.assertFalse(self.manifest_path.exists())
        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(User.objects.filter(username__startswith=DEMO_USER_PREFIX).count(), 0)


class ClearDemoDataTests(DemoDataTestCase):
    def test_clear_removes_tracked_records_and_preserves_unrelated(self):
        keep_user = User.objects.create_user(username='keepme', password='keep-pass-123')
        keep_category = Category.objects.create(name='Categoria Original')
        keep_product = Product.objects.create(
            name='Produto Original', code='ORIG-1', category=keep_category,
            price=Decimal('5.00'), stock_quantity=7, minimum_stock=2,
        )
        keep_person = Person.objects.create(name='Cliente Original', person_type='STAFF')
        keep_sale = Sale.objects.create(
            customer=keep_person, responsible=keep_user, status='COMPLETED',
            payment_method='CASH', subtotal=Decimal('5.00'), total=Decimal('5.00'),
        )
        keep_item = SaleItem.objects.create(
            sale=keep_sale, product=keep_product, quantity=1, unit_price=Decimal('5.00'),
        )
        keep_movement = StockMovement.objects.create(
            product=keep_product, movement_type='SALE', quantity=-1,
            sale=keep_sale, user=keep_user,
        )

        self.seed()
        output = self.clear()
        self.assertIn('Demo dataset cleared.', output)

        self.assertTrue(User.objects.filter(pk=keep_user.pk).exists())
        self.assertTrue(Category.objects.filter(pk=keep_category.pk).exists())
        self.assertTrue(Product.objects.filter(pk=keep_product.pk).exists())
        self.assertTrue(Person.objects.filter(pk=keep_person.pk).exists())
        self.assertTrue(Sale.objects.filter(pk=keep_sale.pk).exists())
        self.assertTrue(SaleItem.objects.filter(pk=keep_item.pk).exists())
        self.assertTrue(StockMovement.objects.filter(pk=keep_movement.pk).exists())

        self.assertFalse(User.objects.filter(username__startswith=DEMO_USER_PREFIX).exists())
        self.assertEqual(Sale.objects.filter(status='COMPLETED').count(), 1)
        self.assertEqual(Sale.objects.filter(status='PENDING').count(), 0)
        self.assertEqual(Sale.objects.filter(status='CANCELLED').count(), 0)
        self.assertEqual(AccountReceivable.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(Category.objects.count(), 1)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Person.objects.count(), 1)
        self.assertEqual(StockMovement.objects.count(), 1)
        self.assertFalse(self.manifest_path.exists())
        self.assert_root_unchanged()

    def test_clear_without_dataset_is_graceful(self):
        output = self.clear()
        self.assertIn('Nothing to clear', output)
        self.assertFalse(self.manifest_path.exists())

    def test_stale_or_corrupt_manifest_is_removed(self):
        stale = {
            'tool': 'seed_demo_data', 'version': 1, 'seed': 1,
            'demo_usernames': [], 'models': {'frontend.Product': [99999999]},
            'counts': {},
        }
        demo_data.write_manifest_atomic(stale)
        self.clear()
        self.assertFalse(self.manifest_path.exists())

        self.manifest_path.write_text('{not json', encoding='utf-8')
        output = self.clear()
        self.assertIn('stale demo manifest', output.lower())
        self.assertFalse(self.manifest_path.exists())

    def test_clear_aborts_on_conflicting_records(self):
        self.seed()
        demo_product = Product.objects.get(code='COX-01')
        rogue = StockMovement.objects.create(
            product=demo_product, movement_type='ADJUSTMENT', quantity=1,
            reason='manual entry after seeding',
        )
        with self.assertRaises(CommandError) as caught:
            self.clear()
        self.assertIn('conflicts', str(caught.exception))
        self.assertTrue(self.manifest_path.exists())
        self.assertTrue(Product.objects.filter(pk=demo_product.pk).exists())

        rogue.delete()
        self.clear()
        self.assertFalse(Product.objects.filter(code='COX-01').exists())
        self.assertFalse(self.manifest_path.exists())

    def test_clear_removes_demo_sessions_but_keeps_others(self):
        self.seed()
        demo_user_pks = list(
            User.objects.filter(username__startswith=DEMO_USER_PREFIX)
            .values_list('pk', flat=True),
        )
        demo_client = Client()
        self.assertTrue(demo_client.login(username=DEMO_USER_ONE, password=DEMO_PASSWORD))
        keeper = User.objects.create_user(username='keepme', password='keep-pass-123')
        keeper_client = Client()
        self.assertTrue(keeper_client.login(username='keepme', password='keep-pass-123'))
        self.assertTrue(demo_data.session_pks_for_users(demo_user_pks))

        self.clear()

        self.assertEqual(demo_data.session_pks_for_users(demo_user_pks), [])
        keeper_sessions = demo_data.session_pks_for_users([keeper.pk])
        self.assertEqual(len(keeper_sessions), 1)
        self.assertEqual(Session.objects.count(), 1)

    def test_reseed_after_clear_works(self):
        self.seed()
        self.clear()
        self.seed()
        self.assertEqual(Sale.objects.count(), 80)
        self.assertEqual(User.objects.filter(username__startswith=DEMO_USER_PREFIX).count(), 6)
        self.assertTrue(self.manifest_path.exists())
        self.clear()
        self.assertEqual(Sale.objects.count(), 0)

    def test_dashboard_returns_to_empty_state_after_clear(self):
        self.seed()
        self.clear()
        html, stats = self.dashboard_stats(username='root', password='root-test-pass')
        self.assertEqual(stats['sales_today'], 0)
        self.assertEqual(stats['daily_revenue'], Decimal('0.00'))
        self.assertEqual(stats['receivables_open_count'], 0)
        self.assertEqual(stats['low_stock_count'], 0)
        self.assertEqual(stats['sales_delta']['value'], '—')
        self.assertEqual(stats['revenue_delta']['value'], '—')
        self.assertNotIn('needs attention', html)
        self.assertEqual(stats['sales_chart']['units'], [0, 0, 0, 0, 0, 0, 0])


class DemoDataSafeguardTests(DemoDataTestCase):
    def test_commands_refuse_to_run_when_disabled(self):
        with self.settings(ALLOW_DEMO_DATA_COMMANDS=False):
            with self.assertRaises(CommandError) as seed_error:
                self.seed()
            self.assertIn('disabled', str(seed_error.exception))
            with self.assertRaises(CommandError) as clear_error:
                self.clear()
            self.assertIn('disabled', str(clear_error.exception))
        self.assertEqual(Sale.objects.count(), 0)
