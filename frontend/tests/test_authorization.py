"""Responsible-based data isolation tests.

Policy under test:

* Superusers and users explicitly granted
  ``frontend.view_all_responsible_data`` see every record.
* Ordinary authenticated users (including ``is_staff`` users) see only
  records attributable to them: their sales, those sales' items,
  receivables and payments. Records with no ownership path (a receivable
  with no sale) stay global-only.
* Forged query parameters can never broaden the visible dataset.
"""
import csv
import io
from decimal import Decimal

from django.contrib.auth.models import AnonymousUser, Permission, User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from frontend.authorization import (
    has_global_access, scoped_payments, scoped_receivables, scoped_sale_items,
    scoped_sales,
)
from frontend.models import (
    AccountReceivable, Category, Payment, Person, Product, Sale, SaleItem,
)


class AuthorizationTestBase(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='test-pass-123')
        self.bob = User.objects.create_user('bob', password='test-pass-123')
        self.staff = User.objects.create_user(
            'zoe-staff', password='test-pass-123', is_staff=True,
        )
        self.admin = User.objects.create_superuser('authz-admin', password='test-pass-123')
        self.viewer = User.objects.create_user('viewer', password='test-pass-123')
        self.viewer.user_permissions.add(Permission.objects.get(
            content_type__app_label='frontend',
            codename='view_all_responsible_data',
        ))

        self.category = Category.objects.create(name='Bebidas')
        self.product = Product.objects.create(
            name='Suco', code='SUCO-AUTHZ', category=self.category,
            price=Decimal('10.00'), stock_quantity=100,
        )
        self.other_product = Product.objects.create(
            name='Bolo', code='BOLO-AUTHZ', category=self.category,
            price=Decimal('20.00'), stock_quantity=100,
        )
        self.person = Person.objects.create(
            name='Cliente Compartilhado', person_type='STUDENT',
        )

        self.alice_sale = self.make_sale(self.alice, self.product, 2, 'ON_ACCOUNT')
        self.bob_sale = self.make_sale(self.bob, self.other_product, 1, 'ON_ACCOUNT')
        self.unassigned_sale = self.make_sale(None, self.product, 1, 'CASH')

        self.alice_ar = AccountReceivable.objects.create(
            person=self.person, sale=self.alice_sale, original_amount=Decimal('20.00'),
            due_date=timezone.localdate(), status='PENDING',
        )
        self.bob_ar = AccountReceivable.objects.create(
            person=self.person, sale=self.bob_sale, original_amount=Decimal('20.00'),
            due_date=timezone.localdate(), status='PENDING',
        )
        self.orphan_ar = AccountReceivable.objects.create(
            person=self.person, original_amount=Decimal('30.00'),
            due_date=timezone.localdate(), status='PENDING',
        )
        self.alice_payment = Payment.objects.create(
            account_receivable=self.alice_ar, amount=Decimal('5.00'),
            method='CASH', responsible_user=self.alice,
        )
        self.bob_payment = Payment.objects.create(
            account_receivable=self.bob_ar, amount=Decimal('7.00'),
            method='PIX', responsible_user=self.bob,
        )

    def make_sale(self, responsible, product, quantity, method='CASH'):
        subtotal = product.price * quantity
        sale = Sale.objects.create(
            customer=self.person, responsible=responsible, status='COMPLETED',
            payment_method=method, subtotal=subtotal, total=subtotal,
            completed_at=timezone.now(),
        )
        SaleItem.objects.create(
            sale=sale, product=product, quantity=quantity, unit_price=product.price,
        )
        return sale

    def login(self, user):
        client = Client()
        client.force_login(user)
        return client

    def sale_codes(self, response):
        return sorted(sale.code for sale in response.context['page_obj'].object_list)


class GlobalAccessHelperTests(AuthorizationTestBase):
    def test_anonymous_and_none_have_no_global_access(self):
        self.assertFalse(has_global_access(None))
        self.assertFalse(has_global_access(AnonymousUser()))

    def test_ordinary_and_staff_users_have_no_global_access(self):
        self.assertFalse(has_global_access(self.alice))
        self.assertFalse(has_global_access(self.staff))

    def test_superuser_and_explicitly_permitted_user_have_global_access(self):
        self.assertTrue(has_global_access(self.admin))
        self.assertTrue(has_global_access(self.viewer))

    def test_scoped_querysets_follow_the_policy(self):
        self.assertEqual(
            set(scoped_sales(self.alice).values_list('pk', flat=True)),
            {self.alice_sale.pk},
        )
        self.assertEqual(
            set(scoped_sale_items(self.alice).values_list('pk', flat=True)),
            set(self.alice_sale.items.values_list('pk', flat=True)),
        )
        self.assertEqual(
            set(scoped_receivables(self.alice).values_list('pk', flat=True)),
            {self.alice_ar.pk},
        )
        self.assertEqual(
            set(scoped_payments(self.alice).values_list('pk', flat=True)),
            {self.alice_payment.pk},
        )
        self.assertEqual(
            set(scoped_sales(self.admin).values_list('pk', flat=True)),
            {self.alice_sale.pk, self.bob_sale.pk, self.unassigned_sale.pk},
        )
        self.assertEqual(
            set(scoped_receivables(self.viewer).values_list('pk', flat=True)),
            {self.alice_ar.pk, self.bob_ar.pk, self.orphan_ar.pk},
        )


class DashboardIsolationTests(AuthorizationTestBase):
    def get_stats(self, user):
        response = self.login(user).get(reverse('frontend:dashboard'))
        self.assertEqual(response.status_code, 200)
        return response.content.decode(), response.context['stats']

    def test_ordinary_user_sees_only_own_sales_and_receivables(self):
        html, stats = self.get_stats(self.alice)
        self.assertEqual(stats['sales_today'], 1)
        self.assertEqual(stats['daily_revenue'], Decimal('20.00'))
        self.assertEqual(stats['receivables_total'], Decimal('15.00'))
        self.assertEqual(stats['receivables_open_count'], 1)
        self.assertEqual(stats['sales_chart']['units'][-1], 2)
        codes = [sale.code for sale in stats['recent_sales']]
        self.assertIn(self.alice_sale.code, codes)
        self.assertNotIn(self.bob_sale.code, codes)
        self.assertNotIn(self.bob_sale.code, html)

    def test_global_user_sees_every_record(self):
        _, stats = self.get_stats(self.admin)
        self.assertEqual(stats['sales_today'], 3)
        self.assertEqual(stats['daily_revenue'], Decimal('50.00'))
        self.assertEqual(stats['receivables_total'], Decimal('58.00'))
        self.assertEqual(stats['receivables_open_count'], 3)
        self.assertEqual(stats['sales_chart']['units'][-1], 4)

    def test_viewer_permission_sees_every_record(self):
        _, stats = self.get_stats(self.viewer)
        self.assertEqual(stats['sales_today'], 3)
        self.assertEqual(stats['receivables_total'], Decimal('58.00'))


class SalesListIsolationTests(AuthorizationTestBase):
    def get_list(self, user, params=None):
        response = self.login(user).get(reverse('frontend:sales_list'), params or {})
        self.assertEqual(response.status_code, 200)
        return response

    def test_ordinary_user_only_sees_own_sales(self):
        response = self.get_list(self.alice)
        self.assertEqual(self.sale_codes(response), [self.alice_sale.code])
        html = response.content.decode()
        self.assertNotIn(self.bob_sale.code, html)
        self.assertNotIn(self.unassigned_sale.code, html)

    def test_search_cannot_reveal_another_users_sale(self):
        response = self.get_list(self.alice, {'q': self.bob_sale.code})
        self.assertEqual(self.sale_codes(response), [])

    def test_staff_status_alone_grants_no_visibility(self):
        response = self.get_list(self.staff)
        self.assertEqual(self.sale_codes(response), [])

    def test_global_users_see_all_sales(self):
        for user in (self.admin, self.viewer):
            with self.subTest(user=user.username):
                response = self.get_list(user)
                self.assertEqual(
                    self.sale_codes(response),
                    [self.alice_sale.code, self.bob_sale.code, self.unassigned_sale.code],
                )


class FinanceIsolationTests(AuthorizationTestBase):
    def get_finance(self, user, params=None):
        response = self.login(user).get(reverse('frontend:finance'), params or {})
        self.assertEqual(response.status_code, 200)
        return response

    def test_ordinary_user_sees_only_own_receivables_and_payments(self):
        response = self.get_finance(self.alice)
        html = response.content.decode()
        self.assertEqual(
            [row.pk for row in response.context['receivables']], [self.alice_ar.pk],
        )
        self.assertEqual(
            [row.pk for row in response.context['payments']], [self.alice_payment.pk],
        )
        self.assertNotIn('R$ 7.00', html)
        self.assertNotIn('R$ 30.00', html)
        self.assertEqual(response.context['total_receivable'], Decimal('15.00'))
        self.assertEqual(response.context['pending_accounts'], 0)

    def test_global_user_sees_every_receivable_and_payment(self):
        response = self.get_finance(self.admin)
        self.assertEqual(
            {row.pk for row in response.context['receivables']},
            {self.alice_ar.pk, self.bob_ar.pk, self.orphan_ar.pk},
        )
        self.assertEqual(
            {row.pk for row in response.context['payments']},
            {self.alice_payment.pk, self.bob_payment.pk},
        )
        self.assertEqual(response.context['total_receivable'], Decimal('58.00'))
        self.assertEqual(response.context['pending_accounts'], 1)

    def test_payment_form_choices_are_scoped(self):
        response = self.get_finance(self.alice)
        queryset = response.context['form'].fields['account_receivable'].queryset
        self.assertEqual(set(queryset.values_list('pk', flat=True)), {self.alice_ar.pk})

    def test_payment_on_foreign_or_orphan_receivable_is_rejected(self):
        for foreign_ar in (self.bob_ar, self.orphan_ar):
            with self.subTest(receivable=foreign_ar.pk):
                before = Payment.objects.count()
                response = self.login(self.alice).post(reverse('frontend:finance'), {
                    'account_receivable': foreign_ar.pk,
                    'amount': '1.00',
                    'method': 'CASH',
                    'notes': '',
                })
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['form'].errors)
                self.assertEqual(Payment.objects.count(), before)
                self.assertFalse(
                    Payment.objects.filter(
                        account_receivable=foreign_ar, amount=Decimal('1.00'),
                    ).exists(),
                )

    def test_payment_on_own_receivable_is_registered(self):
        response = self.login(self.alice).post(reverse('frontend:finance'), {
            'account_receivable': self.alice_ar.pk,
            'amount': '1.00',
            'method': 'CASH',
            'notes': 'own account',
        })
        self.assertEqual(response.status_code, 302)
        payment = Payment.objects.get(notes='own account')
        self.assertEqual(payment.responsible_user, self.alice)


class PeopleBalanceIsolationTests(AuthorizationTestBase):
    def get_people(self, user):
        response = self.login(user).get(reverse('frontend:people'))
        self.assertEqual(response.status_code, 200)
        return response

    def test_ordinary_user_balance_only_counts_visible_receivables(self):
        response = self.get_people(self.alice)
        person = next(
            row for row in response.context['people'] if row.pk == self.person.pk
        )
        self.assertEqual(person.balance, Decimal('-15.00'))

    def test_global_user_balance_counts_every_receivable(self):
        response = self.get_people(self.admin)
        person = next(
            row for row in response.context['people'] if row.pk == self.person.pk
        )
        self.assertEqual(person.balance, Decimal('-58.00'))


class ReportsIsolationTests(AuthorizationTestBase):
    def get_report(self, user, params=None):
        response = self.login(user).get(reverse('frontend:reports'), params or {})
        self.assertEqual(response.status_code, 200)
        return response

    def test_ordinary_user_aggregates_only_include_own_sales(self):
        response = self.get_report(self.alice)
        summary = response.context['summary']
        self.assertEqual(summary['revenue'], Decimal('20.00'))
        self.assertEqual(summary['transactions'], 1)
        self.assertEqual(summary['units'], 2)
        products = response.context['products']
        self.assertEqual(
            [row['name'] for row in products['by_units']], ['Suco'],
        )
        self.assertEqual(products['total_item_revenue'], Decimal('20.00'))
        finance = response.context['finance']
        self.assertEqual(finance['received_total'], Decimal('5.00'))
        self.assertEqual(finance['outstanding_total'], Decimal('15.00'))
        self.assertEqual(finance['open_count'], 1)
        self.assertEqual(
            [sale.code for sale in response.context['page_obj'].object_list],
            [self.alice_sale.code],
        )

    def test_global_user_aggregates_include_every_sale(self):
        for user in (self.admin, self.viewer):
            with self.subTest(user=user.username):
                response = self.get_report(user)
                summary = response.context['summary']
                self.assertEqual(summary['revenue'], Decimal('50.00'))
                self.assertEqual(summary['transactions'], 3)
                self.assertEqual(summary['units'], 4)
                finance = response.context['finance']
                self.assertEqual(finance['received_total'], Decimal('12.00'))
                self.assertEqual(finance['outstanding_total'], Decimal('58.00'))

    def test_forged_responsible_param_cannot_broaden_aggregates(self):
        response = self.get_report(self.alice, {'responsible': self.bob.pk})
        summary = response.context['summary']
        self.assertEqual(summary['revenue'], Decimal('20.00'))
        self.assertEqual(summary['transactions'], 1)
        self.assertEqual(response.context['report'].filters.responsible_id, None)

    def test_responsible_filter_is_offered_only_with_global_access(self):
        self.assertNotIn('report-responsible', self.get_report(self.alice).content.decode())
        self.assertIn('report-responsible', self.get_report(self.admin).content.decode())

    def test_global_user_can_filter_by_responsible(self):
        response = self.get_report(self.admin, {'responsible': self.alice.pk})
        summary = response.context['summary']
        self.assertEqual(summary['transactions'], 1)
        self.assertEqual(summary['revenue'], Decimal('20.00'))

    def test_csv_export_is_scoped(self):
        response = self.login(self.alice).get(reverse('frontend:reports_export'))
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], self.alice_sale.code)
        self.assertNotIn(self.bob_sale.code, [row[0] for row in rows])

        admin_rows = list(csv.reader(io.StringIO(
            self.login(self.admin).get(reverse('frontend:reports_export')).content.decode(),
        )))
        self.assertEqual(len(admin_rows), 4)


class SearchIsolationTests(AuthorizationTestBase):
    def search(self, user, query):
        response = self.login(user).get(reverse('frontend:api_search'), {'q': query})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def group(self, data, group_type):
        for group in data['groups']:
            if group['type'] == group_type:
                return group
        return None

    def test_ordinary_user_cannot_search_another_users_sale(self):
        data = self.search(self.alice, f'sale:{self.bob_sale.code}')
        self.assertIsNone(self.group(data, 'sales'))

        data = self.search(self.alice, f'sale:{self.alice_sale.code}')
        self.assertEqual(
            [item['title'] for item in self.group(data, 'sales')['items']],
            [self.alice_sale.code],
        )

    def test_global_user_can_search_every_sale(self):
        for user in (self.admin, self.viewer):
            with self.subTest(user=user.username):
                data = self.search(user, f'sale:{self.bob_sale.code}')
                self.assertEqual(
                    [item['title'] for item in self.group(data, 'sales')['items']],
                    [self.bob_sale.code],
                )

    def test_shared_catalog_and_people_stay_visible_to_everyone(self):
        for user in (self.alice, self.staff, self.admin):
            with self.subTest(user=user.username):
                products = self.group(self.search(user, 'authz'), 'products')
                self.assertEqual(
                    {item['title'] for item in products['items']},
                    {'Suco', 'Bolo'},
                )
                people = self.group(self.search(user, 'Compartilhado'), 'people')
                self.assertEqual(
                    [item['title'] for item in people['items']],
                    ['Cliente Compartilhado'],
                )


class LoginRequirementTests(AuthorizationTestBase):
    def test_scoped_pages_still_require_login(self):
        anonymous = Client()
        for name in ('dashboard', 'sales_list', 'finance', 'reports', 'people'):
            with self.subTest(page=name):
                response = anonymous.get(reverse(f'frontend:{name}'))
                self.assertEqual(response.status_code, 302)
                self.assertIn('/login/', response['Location'])
