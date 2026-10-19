"""Phase 2.14: server-side list search, filters, sorting, and pagination.

These tests document the shared behavior of the Sales, Products, Inventory,
People, and Finance lists: search fields, filter values, sorted orders, URL
parameter preservation, honest empty states, and the session-backed records
per page. Browser-only interactions (auto-submit, the preferences fetch) are
covered by template/source assertions elsewhere.
"""
import re
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import parse_qs

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from frontend.listsearch import (
    PAGE_SIZE_OPTIONS, build_querystring, normalize_q, paginate,
    parse_iso_date, resolve_page_size, sort_state,
)
from frontend.models import (
    AccountReceivable, Category, Payment, Person, Product, Sale, SaleItem,
)


def backdate(sale, year, month, day, hour=12):
    Sale.objects.filter(pk=sale.pk).update(
        created_at=timezone.make_aware(datetime(year, month, day, hour)),
    )


def table_section(html, tbody_id):
    """Return the markup of one table body, so table assertions never match
    text that belongs to the other table on the same page."""
    section = html.split(f'id="{tbody_id}"', 1)[1]
    return section.split('</tbody>', 1)[0]


class ListSearchHelperTests(TestCase):
    """Unit tests for frontend.listsearch."""

    def setUp(self):
        self.factory = RequestFactory()

    def request(self, url='/list/', params=None, session=None):
        request = self.factory.get(url, params or {})
        request.session = dict(session or {})
        return request

    def test_normalize_q_collapses_whitespace_and_bounds_length(self):
        self.assertEqual(normalize_q('  ana   silva '), 'ana silva')
        self.assertEqual(normalize_q(None), '')
        self.assertEqual(normalize_q('   '), '')
        self.assertEqual(len(normalize_q('x' * 300)), 100)

    def test_parse_iso_date_accepts_iso_and_rejects_garbage(self):
        self.assertEqual(parse_iso_date('2030-01-15'), date(2030, 1, 15))
        self.assertIsNone(parse_iso_date('not-a-date'))
        self.assertIsNone(parse_iso_date(''))

    def test_resolve_page_size_uses_session_allowlist_and_fallback(self):
        self.assertEqual(resolve_page_size(self.request()), 20)
        for value in PAGE_SIZE_OPTIONS:
            self.assertEqual(
                resolve_page_size(self.request(session={'per_page': value})), value,
            )
        for bad in ['15', 0, -10, 'abc', None]:
            self.assertEqual(
                resolve_page_size(self.request(session={'per_page': bad})), 20,
                msg=repr(bad),
            )

    def test_build_querystring_drops_page_and_filters_params(self):
        request = self.request('/list/?q=ana&status=COMPLETED&page=3&empty=')
        self.assertEqual(build_querystring(request), 'q=ana&status=COMPLETED')
        self.assertEqual(build_querystring(request, only=('q',)), 'q=ana')
        self.assertEqual(build_querystring(request, exclude=('q',)), 'status=COMPLETED')

    def test_build_querystring_overrides_replace_and_append(self):
        request = self.request('/list/?q=ana&status=COMPLETED')
        result = parse_qs(build_querystring(
            request, overrides={'q': 'bob', 'sort': 'total'},
        ))
        self.assertEqual(
            result, {'q': ['bob'], 'status': ['COMPLETED'], 'sort': ['total']},
        )

    def test_build_querystring_keeps_repeated_values(self):
        request = self.request('/list/?tag=a&tag=b')
        self.assertEqual(parse_qs(build_querystring(request)), {'tag': ['a', 'b']})

    def test_sort_state_validates_allowlist_and_direction(self):
        allowlist = {'total': ('total', 'id'), 'code': ('code', 'id')}
        sort, direction, order_by = sort_state(
            self.request('/list/?sort=total&dir=asc'), allowlist, 'total',
        )
        self.assertEqual((sort, direction), ('total', 'asc'))
        self.assertEqual(order_by, ('total', 'id'))

        sort, direction, order_by = sort_state(
            self.request('/list/?sort=code'), allowlist, 'total',
        )
        self.assertEqual((sort, direction), ('code', 'asc'))
        self.assertEqual(order_by, ('code', 'id'))

        sort, direction, order_by = sort_state(
            self.request('/list/?sort=drop-table&dir=sideways'), allowlist, 'total',
        )
        self.assertEqual((sort, direction), ('total', 'desc'))
        self.assertEqual(order_by, ('-total', '-id'))

    def test_paginate_degrades_invalid_pages(self):
        for index in range(5):
            Person.objects.create(
                name=f'Pessoa {index}', doc_id=f'DOC-{index}', person_type='STUDENT',
            )
        queryset = Person.objects.order_by('id')
        self.assertEqual(paginate(self.request('/p/?page=2'), queryset, 2).number, 2)
        self.assertEqual(paginate(self.request('/p/?page=abc'), queryset, 2).number, 1)
        self.assertEqual(paginate(self.request('/p/?page=999'), queryset, 2).number, 3)


class SalesListFilterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='sales-ui', password='test-pass-123')
        self.client.force_login(self.user)
        self.ana = Person.objects.create(name='Ana Lima', doc_id='DOC-1', person_type='STUDENT')
        self.bruno = Person.objects.create(name='Bruno Reis', doc_id='DOC-2', person_type='TEACHER')
        self.s1 = Sale.objects.create(
            customer=self.ana, responsible=self.user, status='COMPLETED',
            payment_method='CASH', total=Decimal('10.00'),
        )
        self.s2 = Sale.objects.create(
            customer=self.bruno, responsible=self.user, status='PENDING',
            payment_method='ON_ACCOUNT', total=Decimal('25.00'),
        )
        self.s3 = Sale.objects.create(
            customer=self.ana, responsible=self.user, status='CANCELLED',
            payment_method='CASH', total=Decimal('5.00'),
        )
        backdate(self.s1, 2030, 1, 1)
        backdate(self.s2, 2030, 2, 1)
        backdate(self.s3, 2030, 3, 1)

    def get_html(self, params=None):
        return self.client.get(reverse('frontend:sales_list'), params or {}).content.decode()

    def positions(self, sale_order, html):
        return [html.index(f'<code>{sale.code}</code>') for sale in sale_order]

    def test_default_order_is_newest_first(self):
        html = self.get_html()
        positions = self.positions([self.s3, self.s2, self.s1], html)
        self.assertEqual(positions, sorted(positions))

    def test_search_matches_code_and_customer_name(self):
        html = self.get_html({'q': self.s1.code})
        self.assertIn(f'<code>{self.s1.code}</code>', html)
        self.assertNotIn(f'<code>{self.s2.code}</code>', html)

        html = self.get_html({'q': 'ANA'})
        self.assertIn(f'<code>{self.s1.code}</code>', html)
        self.assertIn(f'<code>{self.s3.code}</code>', html)
        self.assertNotIn(f'<code>{self.s2.code}</code>', html)
        self.assertIn('2 results', html)

    def test_status_and_payment_filters(self):
        html = self.get_html({'status': 'COMPLETED'})
        self.assertIn(f'<code>{self.s1.code}</code>', html)
        self.assertNotIn(f'<code>{self.s2.code}</code>', html)

        html = self.get_html({'payment_method': 'ON_ACCOUNT'})
        self.assertIn(f'<code>{self.s2.code}</code>', html)
        self.assertNotIn(f'<code>{self.s1.code}</code>', html)

    def test_invalid_filter_values_are_ignored(self):
        html = self.get_html({'status': 'DROP', 'payment_method': 'BARTER'})
        for sale in [self.s1, self.s2, self.s3]:
            self.assertIn(f'<code>{sale.code}</code>', html)
        self.assertIn('3 results', html)

    def test_date_range_filters_bound_the_list(self):
        html = self.get_html({'date_from': '2030-02-01'})
        self.assertNotIn(f'<code>{self.s1.code}</code>', html)
        self.assertIn(f'<code>{self.s2.code}</code>', html)

        html = self.get_html({'date_to': '2030-02-01'})
        self.assertIn(f'<code>{self.s1.code}</code>', html)
        self.assertIn(f'<code>{self.s2.code}</code>', html)
        self.assertNotIn(f'<code>{self.s3.code}</code>', html)

    def test_invalid_dates_are_ignored(self):
        html = self.get_html({'date_from': 'yesterday'})
        self.assertIn('3 results', html)

    def test_sorting_by_total_and_code(self):
        html = self.get_html({'sort': 'total', 'dir': 'asc'})
        positions = self.positions([self.s3, self.s1, self.s2], html)
        self.assertEqual(positions, sorted(positions))

        html = self.get_html({'sort': 'code', 'dir': 'desc'})
        positions = self.positions([self.s3, self.s2, self.s1], html)
        self.assertEqual(positions, sorted(positions))

    def test_sort_headers_expose_aria_state_and_preserve_filters(self):
        html = self.get_html({'q': 'Ana', 'sort': 'total', 'dir': 'asc'})
        self.assertEqual(html.count('aria-sort="ascending"'), 1)
        self.assertIn('sort=total&amp;dir=desc', html)
        self.assertIn('sort=created_at&amp;dir=desc', html)
        self.assertIn('sort-indicator', html)

    def test_invalid_sort_falls_back_to_default(self):
        html = self.get_html({'sort': 'total; DROP TABLE'})
        self.assertEqual(len(self.positions([self.s1, self.s2, self.s3], html)), 3)

    def test_items_count_is_annotated(self):
        category = Category.objects.create(name='Snacks')
        product = Product.objects.create(
            name='Coxinha', code='COX-01', category=category,
            price=Decimal('5.00'), stock_quantity=10,
        )
        SaleItem.objects.create(
            sale=self.s1, product=product, quantity=1, unit_price=Decimal('5.00'),
        )
        SaleItem.objects.create(
            sale=self.s1, product=product, quantity=1, unit_price=Decimal('5.00'),
        )
        html = self.get_html({'q': self.s1.code})
        self.assertIn('2 items', html)

    def test_filters_active_shows_clear_link_and_contextual_empty_state(self):
        html = self.get_html({'q': 'nothing-matches'})
        self.assertIn('No sales match your filters', html)
        self.assertIn('Clear filters', html)
        self.assertIn('0 results', html)

    def test_default_empty_state_is_honest_and_has_no_clear_link(self):
        Sale.objects.all().delete()
        html = self.get_html()
        self.assertIn('No sale registered', html)
        self.assertNotIn('Clear filters', html)

    def test_pagination_uses_twenty_default_and_preserves_query(self):
        for index in range(23):
            sale = Sale.objects.create(
                customer=self.ana, responsible=self.user, status='COMPLETED',
                payment_method='CASH', total=Decimal('1.00'),
            )
            backdate(sale, 2030, 4, 1)
        page_one = self.get_html({'q': 'Ana'})
        self.assertIn('25 results', page_one)
        self.assertIn('Page 1 of 2', page_one)
        self.assertIn('q=Ana&page=2', page_one)

        page_two = self.get_html({'q': 'Ana', 'page': 2})
        self.assertIn('Page 2 of 2', page_two)
        self.assertIn('q=Ana&page=1', page_two)

        beyond = self.get_html({'q': 'Ana', 'page': 999})
        self.assertIn('Page 2 of 2', beyond)

    def test_list_is_login_required(self):
        self.client.logout()
        resp = self.client.get(reverse('frontend:sales_list'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])


class ProductListFilterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='products-ui', password='test-pass-123')
        self.client.force_login(self.user)
        self.snacks = Category.objects.create(name='Snacks')
        self.drinks = Category.objects.create(name='Drinks')
        self.coxinha = Product.objects.create(
            name='Coxinha', code='COX-01', category=self.snacks,
            price=Decimal('5.00'), stock_quantity=10,
        )
        self.old_coxinha = Product.objects.create(
            name='Coxinha Velha', code='COX-OLD', category=self.snacks,
            price=Decimal('1.00'), stock_quantity=0, active=False,
        )
        self.suco = Product.objects.create(
            name='Suco', code='SUC-01', category=self.drinks,
            price=Decimal('4.00'), stock_quantity=8,
        )

    def get_html(self, params=None):
        return self.client.get(reverse('frontend:products'), params or {}).content.decode()

    def test_active_is_the_default_and_inactive_state_exposes_hidden_rows(self):
        html = self.get_html()
        self.assertIn('<strong>Coxinha</strong>', html)
        self.assertIn('<strong>Suco</strong>', html)
        self.assertNotIn('Coxinha Velha', html)
        self.assertIn('2 results', html)

        html = self.get_html({'state': 'inactive'})
        self.assertIn('Coxinha Velha', html)
        self.assertNotIn('<strong>Suco</strong>', html)
        self.assertIn('1 result', html)

        html = self.get_html({'state': 'all'})
        self.assertIn('Coxinha Velha', html)
        self.assertIn('3 results', html)

    def test_invalid_state_falls_back_to_active(self):
        html = self.get_html({'state': 'banana'})
        self.assertIn('2 results', html)
        self.assertNotIn('Coxinha Velha', html)

    def test_search_matches_name_and_code_case_insensitively(self):
        html = self.get_html({'q': 'cox'})
        self.assertIn('<strong>Coxinha</strong>', html)
        self.assertNotIn('Coxinha Velha', html)

        html = self.get_html({'q': 'suc-01'})
        self.assertIn('<strong>Suco</strong>', html)
        self.assertNotIn('COX-01', html)

        html = self.get_html({'q': 'COX', 'state': 'all'})
        self.assertIn('Coxinha Velha', html)

    def test_category_filter_uses_its_id(self):
        html = self.get_html({'category': self.drinks.pk})
        self.assertIn('<strong>Suco</strong>', html)
        self.assertNotIn('COX-01', html)

        html = self.get_html({'category': 'not-a-number'})
        self.assertIn('2 results', html)

    def test_query_is_escaped_in_the_toolbar(self):
        html = self.get_html({'q': '<script>alert(1)</script>'})
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>alert(1)</script>', html)

    def test_pagination_preserves_search_and_state(self):
        for index in range(25):
            Product.objects.create(
                name=f'Item {index:02d}', code=f'IT-{index:02d}', category=self.snacks,
                price=Decimal('1.00'), stock_quantity=1,
            )
        html = self.get_html({'q': 'Item', 'state': 'active'})
        self.assertIn('25 results', html)
        self.assertIn('Page 1 of 2', html)
        self.assertIn('q=Item', html)
        self.assertIn('state=active', html)
        self.assertIn('page=2', html)


class InventoryListFilterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='inventory-ui', password='test-pass-123')
        self.client.force_login(self.user)
        self.drinks = Category.objects.create(name='Bebidas')
        self.sweets = Category.objects.create(name='Doces')
        self.normal = Product.objects.create(
            name='Normal Item', code='N1', category=self.drinks,
            price=Decimal('2.00'), stock_quantity=10, minimum_stock=5,
        )
        self.low = Product.objects.create(
            name='Low Item', code='L1', category=self.drinks,
            price=Decimal('3.00'), stock_quantity=3, minimum_stock=5,
        )
        self.out = Product.objects.create(
            name='Out Item', code='O1', category=self.sweets,
            price=Decimal('4.00'), stock_quantity=0, minimum_stock=5,
        )
        self.inactive = Product.objects.create(
            name='Inactive Item', code='I1', category=self.sweets,
            price=Decimal('5.00'), stock_quantity=8, minimum_stock=5, active=False,
        )

    def get_html(self, params=None):
        return self.client.get(reverse('frontend:inventory'), params or {}).content.decode()

    def row_statuses(self, html):
        return re.findall(r'<tr class="product-row" data-status="([A-Z_]+)"', html)

    def test_status_filter_matches_the_rendered_badges(self):
        cases = {
            'NORMAL': ['NORMAL'],
            'LOW': ['LOW'],
            'OUT_OF_STOCK': ['OUT_OF_STOCK'],
            'INACTIVE': ['INACTIVE'],
        }
        for status, expected in cases.items():
            html = self.get_html({'status': status})
            self.assertEqual(sorted(self.row_statuses(html)), sorted(expected), msg=status)
            self.assertIn('1 result', html)
            self.assertIn(f'data-status="{status}"', html)

    def test_invalid_status_shows_everything(self):
        html = self.get_html({'status': 'SOLD_OUT'})
        self.assertEqual(len(self.row_statuses(html)), 4)

    def test_search_and_category_filters_combine(self):
        html = self.get_html({'q': 'item', 'category': self.sweets.pk})
        self.assertEqual(
            sorted(self.row_statuses(html)), ['INACTIVE', 'OUT_OF_STOCK'],
        )

        html = self.get_html({'q': 'low'})
        self.assertEqual(self.row_statuses(html), ['LOW'])

        html = self.get_html({'q': 'N1'})
        self.assertEqual(self.row_statuses(html), ['NORMAL'])

    def test_summary_cards_describe_the_whole_catalog_under_filters(self):
        html = self.get_html({'status': 'OUT_OF_STOCK'})
        self.assertIn('<div class="stat-value" id="total-items">3</div>', html)
        self.assertIn('R$ 29.00', html)
        self.assertIn('<div class="stat-value" id="low-stock">1</div>', html)
        self.assertIn('<div class="stat-value" id="out-of-stock">1</div>', html)

    def test_filters_active_shows_clear_link_and_contextual_empty_state(self):
        html = self.get_html({'q': 'nothing-matches'})
        self.assertIn('No inventory items match your filters', html)
        self.assertIn('Clear filters', html)

    def test_pagination_appears_with_more_than_twenty_rows(self):
        for index in range(20):
            Product.objects.create(
                name=f'Item {index:02d}', code=f'IT-{index:02d}', category=self.drinks,
                price=Decimal('1.00'), stock_quantity=1,
            )
        html = self.get_html()
        self.assertIn('24 results', html)
        self.assertIn('Page 1 of 2', html)
        self.assertIn('page=2', html)

        page_two = self.get_html({'page': 2})
        self.assertIn('Page 2 of 2', page_two)
        self.assertEqual(len(self.row_statuses(page_two)), 4)


class PeopleListSearchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='people-ui', password='test-pass-123')
        self.client.force_login(self.user)
        self.ana = Person.objects.create(
            name='Ana Lima', doc_id='DOC-1', person_type='STUDENT',
            email='ana@example.com', phone='555-0100',
        )
        self.bruno = Person.objects.create(
            name='Bruno Reis', doc_id='DOC-2', person_type='TEACHER',
        )
        self.inactive = Person.objects.create(
            name='Carla Inativa', doc_id='DOC-3', person_type='STAFF', active=False,
        )
        self.sale = Sale.objects.create(
            customer=self.ana, responsible=self.user, status='COMPLETED',
            payment_method='ON_ACCOUNT', total=Decimal('12.50'),
        )
        self.account = AccountReceivable.objects.create(
            person=self.ana, sale=self.sale, original_amount=Decimal('12.50'),
            due_date='2030-01-15', status='PENDING',
        )
        Payment.objects.create(
            account_receivable=self.account, amount=Decimal('2.50'), method='CASH',
        )

    def get_html(self, params=None):
        return self.client.get(reverse('frontend:people'), params or {}).content.decode()

    def test_default_view_is_active_and_state_filter_exposes_inactive(self):
        html = self.get_html()
        self.assertIn('Ana Lima', html)
        self.assertIn('Bruno Reis', html)
        self.assertNotIn('Carla Inativa', html)

        html = self.get_html({'state': 'inactive'})
        self.assertIn('Carla Inativa', html)
        self.assertNotIn('Ana Lima', html)

        html = self.get_html({'state': 'all'})
        self.assertIn('Carla Inativa', html)
        self.assertIn('3 results', html)

    def test_invalid_state_falls_back_to_active(self):
        html = self.get_html({'state': 'zombie'})
        self.assertNotIn('Carla Inativa', html)

    def test_type_filter_and_search_by_name_or_registration(self):
        html = self.get_html({'type': 'TEACHER'})
        self.assertIn('Bruno Reis', html)
        self.assertNotIn('Ana Lima', html)

        html = self.get_html({'q': 'doc-1'})
        self.assertIn('Ana Lima', html)
        self.assertNotIn('Bruno Reis', html)

        html = self.get_html({'q': 'lima'})
        self.assertIn('Ana Lima', html)

    def test_count_line_names_the_query(self):
        html = self.get_html({'q': 'Ana'})
        self.assertIn('1 result', html)
        self.assertIn('matching \u201cAna\u201d', html)

    def test_balance_survives_filtering_and_contact_fields_stay_private(self):
        html = self.get_html({'q': 'Ana'})
        self.assertIn('R$ -10.00', html)
        self.assertNotIn('ana@example.com', html)
        self.assertNotIn('555-0100', html)

    def test_empty_state_is_contextual(self):
        html = self.get_html({'q': 'zzz'})
        self.assertIn('No people match your search', html)
        self.assertIn('Clear the search', html)

    def test_pagination_preserves_query(self):
        for index in range(25):
            Person.objects.create(
                name=f'Pessoa {index:02d}', doc_id=f'DOC-{index + 10}',
                person_type='STUDENT',
            )
        html = self.get_html({'q': 'Pessoa'})
        self.assertIn('25 results', html)
        self.assertIn('Page 1 of 2', html)
        self.assertIn('q=Pessoa', html)
        self.assertIn('page=2', html)


class FinanceListSearchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='finance-ui', password='test-pass-123')
        self.client.force_login(self.user)
        self.maria = Person.objects.create(name='Maria Souza', doc_id='DOC-9', person_type='STUDENT')
        self.joao = Person.objects.create(name='Joao Alves', doc_id='DOC-4', person_type='STAFF')
        self.sale = Sale.objects.create(
            customer=self.maria, responsible=self.user, status='COMPLETED',
            payment_method='ON_ACCOUNT', total=Decimal('12.50'),
            notes='Monthly meal plan',
        )
        self.r1 = AccountReceivable.objects.create(
            person=self.maria, sale=self.sale, original_amount=Decimal('12.50'),
            due_date='2030-01-15', status='PENDING',
        )
        Payment.objects.create(
            account_receivable=self.r1, amount=Decimal('2.50'), method='CASH',
            notes='partial payment',
        )
        self.r2 = self.make_receivable(
            self.joao, Decimal('20.00'), '2030-02-15', 'PAID',
        )
        self.r3 = self.make_receivable(
            self.joao, Decimal('30.00'), '2030-03-15', 'CANCELLED',
        )
        self.r4 = self.make_receivable(
            self.joao, Decimal('20.00'), '2031-01-01', 'PENDING',
        )

    def make_receivable(self, person, amount, due_date, status):
        """Receivable reachable from a sale owned by the signed-in user."""
        sale = Sale.objects.create(
            customer=person, responsible=self.user, status='COMPLETED',
            payment_method='ON_ACCOUNT', total=amount,
        )
        return AccountReceivable.objects.create(
            person=person, sale=sale, original_amount=amount,
            due_date=due_date, status=status,
        )

    def get_html(self, params=None):
        return self.client.get(reverse('frontend:finance'), params or {}).content.decode()

    def receivables(self, html):
        return table_section(html, 'receivables-table')

    def payments(self, html):
        return table_section(html, 'recent-payments')

    def test_default_view_shows_open_accounts_only(self):
        html = self.get_html()
        rows = self.receivables(html)
        self.assertIn('R$ 12.50', rows)
        self.assertIn('Pending', rows)
        self.assertNotIn('Cancelled', rows)
        self.assertNotIn('Paid', rows)
        self.assertIn('2 results', html)

    def test_explicit_status_replaces_the_open_default(self):
        html = self.get_html({'rstatus': 'PAID'})
        rows = self.receivables(html)
        self.assertIn('Paid', rows)
        self.assertNotIn('Maria Souza', rows)
        self.assertIn('1 result', html)

        html = self.get_html({'rstatus': 'CANCELLED'})
        rows = self.receivables(html)
        self.assertIn('Cancelled', rows)
        self.assertIn('1 result', html)

    def test_invalid_status_falls_back_to_open_accounts(self):
        html = self.get_html({'rstatus': 'FORGOTTEN'})
        self.assertIn('2 results', html)

    def test_search_matches_person_sale_code_and_notes(self):
        for query in ['maria', self.sale.code, 'meal plan']:
            html = self.get_html({'rq': query})
            rows = self.receivables(html)
            self.assertIn('R$ 12.50', rows, msg=query)
            self.assertIn('1 result', html, msg=query)

    def test_due_date_range_filters(self):
        html = self.get_html({'due_from': '2030-06-01'})
        rows = self.receivables(html)
        self.assertIn('R$ 20.00', rows)
        self.assertNotIn('R$ 12.50', rows)

        html = self.get_html({'due_to': '2030-06-01'})
        rows = self.receivables(html)
        self.assertIn('R$ 12.50', rows)
        self.assertIn('1 result', html)

    def test_paid_and_remaining_columns_are_computed(self):
        rows = self.receivables(self.get_html({'rq': 'maria'}))
        self.assertIn('R$ 12.50', rows)
        self.assertIn('R$ 2.50', rows)
        self.assertIn('R$ 10.00', rows)

    def test_receivable_sorting(self):
        html = self.get_html({'sort': 'amount', 'dir': 'desc'})
        rows = self.receivables(html)
        self.assertLess(rows.index('R$ 20.00'), rows.index('R$ 12.50'))
        self.assertEqual(html.count('aria-sort="descending"'), 1)

        html = self.get_html({'sort': 'amount', 'dir': 'asc'})
        rows = self.receivables(html)
        self.assertLess(rows.index('R$ 12.50'), rows.index('R$ 20.00'))
        self.assertEqual(html.count('aria-sort="ascending"'), 1)

        rows = self.receivables(self.get_html({'sort': 'person', 'dir': 'asc'}))
        self.assertLess(rows.index('Joao Alves'), rows.index('Maria Souza'))

    def test_receivable_sort_headers_keep_the_filters(self):
        html = self.get_html({'rq': 'maria', 'sort': 'due_date'})
        self.assertIn('rq=maria', html)
        self.assertIn('sort=person&amp;dir=asc', html)

    def test_receivable_pagination_uses_rpage_and_keeps_sorting(self):
        for index in range(25):
            self.make_receivable(self.maria, Decimal('1.00'), '2030-05-01', 'PENDING')
        html = self.get_html({'sort': 'amount'})
        self.assertIn('27 results', html)
        self.assertIn('rpage=2', html)
        self.assertIn('sort=amount', html)

        page_two = self.get_html({'sort': 'amount', 'rpage': 2})
        self.assertIn('Page 2 of 2', page_two)

    def test_payments_search_method_and_date_filters(self):
        second = Payment.objects.create(
            account_receivable=self.r4, amount=Decimal('5.00'), method='PIX',
            notes='pix transfer',
        )
        Payment.objects.filter(pk=second.pk).update(payment_date=date(2030, 7, 1))

        rows = self.payments(self.get_html({'pq': 'maria'}))
        self.assertIn('R$ 2.50', rows)
        self.assertNotIn('R$ 5.00', rows)

        rows = self.payments(self.get_html({'pq': 'pix transfer'}))
        self.assertIn('R$ 5.00', rows)
        self.assertIn('PIX', rows)

        rows = self.payments(self.get_html({'pmethod': 'CASH'}))
        self.assertIn('R$ 2.50', rows)
        self.assertNotIn('R$ 5.00', rows)

        rows = self.payments(self.get_html({'paid_from': '2030-06-01'}))
        self.assertIn('R$ 5.00', rows)
        self.assertNotIn('R$ 2.50', rows)

        rows = self.payments(self.get_html({'paid_to': '2030-06-01'}))
        self.assertIn('R$ 2.50', rows)
        self.assertNotIn('R$ 5.00', rows)

    def test_payments_are_newest_first(self):
        Payment.objects.create(
            account_receivable=self.r4, amount=Decimal('5.00'), method='PIX',
        )
        rows = self.payments(self.get_html())
        self.assertLess(rows.index('R$ 5.00'), rows.index('R$ 2.50'))

    def test_receivable_filters_leave_the_payments_table_alone(self):
        html = self.get_html({'rq': 'does-not-exist'})
        self.assertIn('No receivables match your filters', self.receivables(html))
        self.assertIn('R$ 2.50', self.payments(html))

    def test_payments_pagination_and_empty_state(self):
        html = self.get_html({'pq': 'zzz'})
        self.assertIn('No payments match your filters', self.payments(html))
        self.assertIn('0 results', html)

        AccountReceivable.objects.filter(pk=self.r4.pk).update(
            original_amount=Decimal('100.00'),
        )
        for index in range(25):
            Payment.objects.create(
                account_receivable=self.r4, amount=Decimal('1.00'), method='CASH',
            )
        html = self.get_html()
        self.assertIn('ppage=2', html)
        self.assertIn('Page 1 of 2', html)


class ListControlsConsistencyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='controls-ui', password='test-pass-123')
        self.client.force_login(self.user)

    def test_every_list_page_has_get_toolbar_count_and_status(self):
        expectations = {
            'sales_list': 1,
            'products': 1,
            'inventory': 1,
            'people': 1,
            'finance': 2,
        }
        for url_name, count in expectations.items():
            with self.subTest(page=url_name):
                html = self.client.get(reverse(f'frontend:{url_name}')).content.decode()
                self.assertEqual(html.count('list-toolbar-form'), count)
                self.assertEqual(html.count('role="search"'), count + 1)
                self.assertEqual(html.count('class="list-count" role="status"'), count)
                self.assertEqual(html.count('method="get"'), count)

    def test_single_page_lists_render_no_pagination(self):
        html = self.client.get(reverse('frontend:sales_list')).content.decode()
        self.assertNotIn('table-pagination', html)
