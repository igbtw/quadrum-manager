import re
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from frontend.models import Category, Person, Product, Sale
from frontend.search import (
    DOC_TOPICS, PAGE_REGISTRY, SEARCH_PREFIXES, SEARCH_PROMPTS,
    parse_search_query, registry_matches,
)


class GlobalSearchApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='searchuser', password='test-pass-123')
        self.category = Category.objects.create(name='Snacks')
        self.product = Product.objects.create(
            name='Coxinha', code='COX-01', category=self.category,
            price=Decimal('5.00'), stock_quantity=10,
        )
        self.inactive_product = Product.objects.create(
            name='Coxinha Velha', code='COX-OLD', category=self.category,
            price=Decimal('1.00'), stock_quantity=0, active=False,
        )
        self.person = Person.objects.create(
            name='Ana Silva', doc_id='DOC-77', person_type='STUDENT',
            email='ana@example.com', phone='555-0100',
        )
        self.inactive_person = Person.objects.create(
            name='Ana Inativa', doc_id='DOC-88', person_type='STUDENT', active=False,
        )
        self.sale = Sale.objects.create(
            customer=self.person, responsible=self.user, status='COMPLETED',
            payment_method='CASH', subtotal=Decimal('10.00'), total=Decimal('10.00'),
        )

    def search(self, query):
        return self.client.get(reverse('frontend:api_search'), {'q': query})

    def group(self, data, group_type):
        for group in data['groups']:
            if group['type'] == group_type:
                return group
        return None

    def test_anonymous_redirected_to_login(self):
        resp = self.search('coxinha')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])

    def test_post_not_allowed(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('frontend:api_search'), {'q': 'coxinha'})
        self.assertEqual(resp.status_code, 405)

    def test_empty_short_and_whitespace_queries_return_no_groups(self):
        self.client.force_login(self.user)
        for query in ['', '   ', 'c']:
            resp = self.search(query)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()['groups'], [])

    def test_product_search_is_case_insensitive_and_excludes_inactive(self):
        self.client.force_login(self.user)
        data = self.search('  COXINHA  ').json()
        product_group = self.group(data, 'products')
        self.assertIsNotNone(product_group)
        self.assertEqual([item['title'] for item in product_group['items']], ['Coxinha'])
        self.assertEqual(
            product_group['items'][0]['url'],
            reverse('frontend:products') + '?q=COX-01',
        )

    def test_product_search_by_code(self):
        self.client.force_login(self.user)
        data = self.search('cox-01').json()
        product_group = self.group(data, 'products')
        self.assertEqual([item['title'] for item in product_group['items']], ['Coxinha'])

    def test_product_results_are_limited(self):
        for index in range(7):
            Product.objects.create(
                name=f'TestItem {index}', code=f'TI-{index}', category=self.category,
                price=Decimal('1.00'), stock_quantity=1,
            )
        self.client.force_login(self.user)
        data = self.search('TestItem').json()
        self.assertEqual(len(self.group(data, 'products')['items']), 5)

    def test_people_search_excludes_inactive_and_sensitive_fields(self):
        self.client.force_login(self.user)
        data = self.search('ana').json()
        people_group = self.group(data, 'people')
        self.assertEqual([item['title'] for item in people_group['items']], ['Ana Silva'])
        item = people_group['items'][0]
        self.assertEqual(set(item), {'title', 'subtitle', 'url', 'icon'})
        self.assertNotIn('ana@example.com', str(data))
        self.assertNotIn('555-0100', str(data))
        self.assertEqual(item['url'], reverse('frontend:people') + '?q=Ana+Silva')

    def test_sale_search_by_code_and_customer(self):
        self.client.force_login(self.user)
        by_code = self.search(self.sale.code).json()
        self.assertEqual(
            self.group(by_code, 'sales')['items'][0]['title'], self.sale.code,
        )
        by_customer = self.search('Ana Silva').json()
        sales_group = self.group(by_customer, 'sales')
        self.assertEqual([item['title'] for item in sales_group['items']], [self.sale.code])
        self.assertEqual(
            sales_group['items'][0]['url'],
            reverse('frontend:sales_list') + f'?q={self.sale.code}',
        )

    def test_overlong_query_is_bounded(self):
        self.client.force_login(self.user)
        resp = self.search('x' * 300)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['groups'], [])


class SearchPrefixApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='prefixuser', password='test-pass-123')
        self.category = Category.objects.create(name='Snacks')
        Product.objects.create(
            name='Coxinha', code='COX-01', category=self.category,
            price=Decimal('5.00'), stock_quantity=10,
        )
        Product.objects.create(
            name='Coxinha Velha', code='COX-OLD', category=self.category,
            price=Decimal('1.00'), stock_quantity=0, active=False,
        )
        self.person = Person.objects.create(
            name='Ana Silva', doc_id='DOC-77', person_type='STUDENT',
            email='ana@example.com', phone='555-0100',
        )
        self.sale = Sale.objects.create(
            customer=self.person, responsible=self.user, status='COMPLETED',
            payment_method='CASH', subtotal=Decimal('10.00'), total=Decimal('10.00'),
        )
        self.client.force_login(self.user)

    def search(self, query):
        return self.client.get(reverse('frontend:api_search'), {'q': query})

    def test_page_prefix_restricts_to_pages(self):
        data = self.search('page:inventory').json()
        self.assertEqual([group['type'] for group in data['groups']], ['pages'])
        self.assertEqual(data['prefix'], 'pages')
        item = data['groups'][0]['items'][0]
        self.assertEqual(item['title'], 'Inventory')
        self.assertEqual(item['url'], reverse('frontend:inventory'))

    def test_doc_prefix_restricts_to_documentation_topics(self):
        data = self.search('doc:receivables').json()
        self.assertEqual([group['type'] for group in data['groups']], ['docs'])
        self.assertEqual(data['prefix'], 'docs')
        items = data['groups'][0]['items']
        titles = [item['title'] for item in items]
        self.assertIn('Finance and Receivables', titles)
        self.assertIn('Dashboard', titles)
        finance = next(item for item in items if item['title'] == 'Finance and Receivables')
        self.assertEqual(
            finance['url'],
            reverse('frontend:documentation_topic', args=['finance']),
        )

    def test_doc_prefix_matches_topic_keywords(self):
        data = self.search('doc:getting started').json()
        items = data['groups'][0]['items']
        self.assertEqual(
            [item['title'] for item in items],
            ['Getting Started'],
        )
        self.assertEqual(
            items[0]['url'],
            reverse('frontend:documentation_topic', args=['getting-started']),
        )

    def test_product_prefix_restricts_to_products(self):
        data = self.search('product:cox-01').json()
        self.assertEqual([group['type'] for group in data['groups']], ['products'])
        self.assertEqual(data['prefix'], 'products')
        self.assertEqual(data['groups'][0]['items'][0]['title'], 'Coxinha')

    def test_person_prefix_restricts_to_people(self):
        data = self.search('person:ana').json()
        self.assertEqual([group['type'] for group in data['groups']], ['people'])
        self.assertEqual(data['prefix'], 'people')
        self.assertEqual(
            [item['title'] for item in data['groups'][0]['items']],
            ['Ana Silva'],
        )

    def test_person_prefix_result_navigates_to_filtered_listing(self):
        data = self.search('person:DOC-77').json()
        item = data['groups'][0]['items'][0]
        self.assertEqual(item['title'], 'Ana Silva')
        self.assertEqual(item['url'], reverse('frontend:people') + '?q=Ana+Silva')

    def test_sale_prefix_restricts_to_sales(self):
        data = self.search(f'sale:{self.sale.code}').json()
        self.assertEqual([group['type'] for group in data['groups']], ['sales'])
        self.assertEqual(data['prefix'], 'sales')
        self.assertEqual(data['groups'][0]['items'][0]['title'], self.sale.code)

    def test_prefixes_are_case_insensitive_and_trimmed(self):
        data = self.search('  PRODUCT:   Coxinha  ').json()
        self.assertEqual([group['type'] for group in data['groups']], ['products'])
        self.assertEqual(
            [item['title'] for item in data['groups'][0]['items']],
            ['Coxinha'],
        )

    def test_empty_prefixed_query_returns_prompt(self):
        data = self.search('product:').json()
        self.assertEqual(data['groups'], [])
        self.assertEqual(data['prefix'], 'products')
        self.assertIn('product:', data['prompt'])

        spaced = self.search('person:   ').json()
        self.assertEqual(spaced['groups'], [])
        self.assertEqual(spaced['prefix'], 'people')
        self.assertIn('person:', spaced['prompt'])

    def test_doc_prefix_without_term_shows_prompt(self):
        data = self.search('doc:').json()
        self.assertEqual(data['groups'], [])
        self.assertEqual(data['prefix'], 'docs')
        self.assertIn('doc:', data['prompt'])

    def test_unknown_prefix_is_ordinary_text(self):
        Product.objects.create(
            name='Nota: Fiscal', code='NF-1', category=self.category,
            price=Decimal('1.00'), stock_quantity=1,
        )
        data = self.search('nota:').json()
        self.assertNotIn('prompt', data)
        self.assertEqual([group['type'] for group in data['groups']], ['products'])
        self.assertEqual(data['groups'][0]['items'][0]['title'], 'Nota: Fiscal')

    def test_prefixed_search_requires_two_characters(self):
        data = self.search('product:r').json()
        self.assertEqual(data['groups'], [])
        self.assertNotIn('prompt', data)

    def test_prefixed_results_are_limited(self):
        for index in range(7):
            Product.objects.create(
                name=f'TestItem {index}', code=f'TI-{index}', category=self.category,
                price=Decimal('1.00'), stock_quantity=1,
            )
        data = self.search('product:TestItem').json()
        self.assertEqual(len(data['groups'][0]['items']), 5)

    def test_prefixed_search_never_exposes_sensitive_fields(self):
        data = self.search('person:ana').json()
        self.assertNotIn('ana@example.com', str(data))
        self.assertNotIn('555-0100', str(data))

    def test_unprefixed_search_covers_pages_and_docs(self):
        data = self.search('inventory').json()
        types = [group['type'] for group in data['groups']]
        self.assertEqual(types, ['pages', 'docs'])
        self.assertNotIn('prefix', data)

    def test_overlong_prefixed_query_is_bounded(self):
        data = self.search('product:' + 'x' * 300).json()
        self.assertEqual(data['groups'], [])
        self.assertNotIn('prompt', data)


class SearchQueryParserTests(TestCase):
    def test_recognized_prefixes_map_to_group_types(self):
        cases = {
            'page:inventory': 'pages',
            'doc:receivables': 'docs',
            'product:rice': 'products',
            'person:maria': 'people',
            'sale:1042': 'sales',
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                group_type, term = parse_search_query(query)
                self.assertEqual(group_type, expected)
                self.assertTrue(term)

    def test_prefixes_are_case_insensitive(self):
        self.assertEqual(parse_search_query('PAGE:Inventory'), ('pages', 'Inventory'))
        self.assertEqual(parse_search_query('Product: Rice'), ('products', 'Rice'))

    def test_unprefixed_query_keeps_text(self):
        self.assertEqual(parse_search_query('  Coxinha  '), (None, 'Coxinha'))

    def test_empty_prefixed_query_yields_empty_term(self):
        self.assertEqual(parse_search_query('product:'), ('products', ''))
        self.assertEqual(parse_search_query('doc:   '), ('docs', ''))

    def test_unknown_prefix_remains_ordinary_text(self):
        self.assertEqual(parse_search_query('note: rice'), (None, 'note: rice'))
        self.assertEqual(parse_search_query('a:b'), (None, 'a:b'))

    def test_none_and_empty_inputs(self):
        self.assertEqual(parse_search_query(None), (None, ''))
        self.assertEqual(parse_search_query(''), (None, ''))

    def test_registry_matches_title_and_keywords(self):
        entries = [
            {'title': 'Alpha', 'keywords': 'first letter'},
            {'title': 'Beta', 'keywords': 'second letter'},
        ]
        self.assertEqual(
            [entry['title'] for entry in registry_matches(entries, 'ALPHA')],
            ['Alpha'],
        )
        self.assertEqual(
            [entry['title'] for entry in registry_matches(entries, 'letter')],
            ['Alpha', 'Beta'],
        )
        self.assertEqual(registry_matches(entries, ''), [])

    def test_every_prefix_has_a_prompt_for_its_group(self):
        self.assertEqual(set(SEARCH_PREFIXES), {'page', 'doc', 'product', 'person', 'sale'})
        for token, group_type in SEARCH_PREFIXES.items():
            with self.subTest(token=token):
                self.assertIn(token + ':', SEARCH_PROMPTS[group_type])


class SearchRegistrySyncTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='syncuser', password='test-pass-123')
        self.client.force_login(self.user)

    def island_entries(self, html, island_id):
        match = re.search(
            r'<ul id="%s"[^>]*>(.*?)</ul>' % island_id, html, re.S,
        )
        self.assertIsNotNone(match)
        return re.findall(
            r'<a href="([^"]+)" data-icon="([^"]+)" data-keywords="([^"]+)">([^<]+)</a>',
            match.group(1),
        )

    def test_page_island_matches_page_registry(self):
        html = self.client.get(reverse('frontend:dashboard')).content.decode()
        entries = self.island_entries(html, 'searchPageData')
        self.assertEqual(len(entries), len(PAGE_REGISTRY))
        for (url, icon, keywords, title), registry in zip(entries, PAGE_REGISTRY):
            with self.subTest(page=title):
                self.assertEqual(url, reverse(registry['url_name']))
                self.assertEqual(icon, registry['icon'])
                self.assertEqual(keywords, registry['keywords'])
                self.assertEqual(title, registry['title'])

    def test_doc_island_matches_doc_topic_registry(self):
        html = self.client.get(reverse('frontend:dashboard')).content.decode()
        entries = self.island_entries(html, 'searchDocData')
        self.assertEqual(len(entries), len(DOC_TOPICS))
        for (url, icon, keywords, title), registry in zip(entries, DOC_TOPICS):
            with self.subTest(topic=title):
                self.assertEqual(
                    url,
                    reverse('frontend:documentation_topic', args=[registry['slug']]),
                )
                self.assertEqual(icon, registry['icon'])
                self.assertEqual(keywords, registry['keywords'])
                self.assertEqual(title, registry['title'])

    def test_every_registry_topic_has_a_working_page(self):
        for registry in DOC_TOPICS:
            url = reverse('frontend:documentation_topic', args=[registry['slug']])
            with self.subTest(topic=registry['slug']):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200)
                self.assertContains(resp, registry['title'])


class PeopleListingFilterTests(TestCase):
    """The palette sends people results to /people/?q=<name>; these tests cover
    the destination listing that receives that query."""

    def setUp(self):
        self.user = User.objects.create_user(username='people-search', password='test-pass-123')
        self.client.force_login(self.user)
        self.ana = Person.objects.create(
            name='Ana Silva', doc_id='DOC-77', person_type='STUDENT',
            email='ana@example.com', phone='555-0100',
        )
        Person.objects.create(name='Bruno Costa', doc_id='DOC-88', person_type='TEACHER')

    def get_html(self, query=None):
        url = reverse('frontend:people')
        if query is not None:
            url += '?' + urlencode({'q': query})
        return self.client.get(url).content.decode()

    def test_name_query_filters_listing_and_shows_banner(self):
        html = self.get_html('ana')
        self.assertIn('Ana Silva', html)
        self.assertNotIn('Bruno Costa', html)
        self.assertIn('matching “ana”', html)

    def test_doc_query_filters_listing(self):
        html = self.get_html('DOC-88')
        self.assertIn('Bruno Costa', html)
        self.assertNotIn('Ana Silva', html)

    def test_no_match_shows_honest_empty_state(self):
        html = self.get_html('nobodyhere')
        self.assertIn('No people match your search', html)
        self.assertIn('Clear the search', html)
        self.assertNotIn('No people registered', html)

    def test_whitespace_is_normalized_and_query_bounded(self):
        resp = self.client.get(reverse('frontend:people'), {'q': '  ana   silva  '})
        self.assertContains(resp, 'Ana Silva')
        long_resp = self.client.get(reverse('frontend:people'), {'q': 'x' * 300})
        self.assertEqual(long_resp.status_code, 200)

    def test_unfiltered_listing_has_no_banner(self):
        html = self.get_html()
        self.assertNotIn('matching “', html)
        self.assertIn('Ana Silva', html)

    def test_listing_never_shows_sensitive_fields(self):
        html = self.get_html()
        self.assertNotIn('ana@example.com', html)
        self.assertNotIn('555-0100', html)

    def test_anonymous_redirected_to_login(self):
        self.client.logout()
        resp = self.client.get(reverse('frontend:people') + '?' + urlencode({'q': 'ana'}))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])


class DialogMarkupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='dialoguser', password='test-pass-123')

    def test_authenticated_page_renders_dialogs_once_and_post_logout_form(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse('frontend:dashboard')).content.decode()

        self.assertEqual(html.count('id="logoutDialog"'), 1)
        self.assertEqual(html.count('id="searchPalette"'), 1)
        self.assertEqual(html.count('id="preferencesDialog"'), 1)
        self.assertEqual(html.count('id="chartExpandDialog"'), 1)
        self.assertEqual(html.count('id="searchPageData"'), 1)
        self.assertIn('role="combobox"', html)
        self.assertIn('role="listbox"', html)
        self.assertEqual(html.count('aria-modal="true"'), 5)
        self.assertEqual(html.count('id="globalSearchTrigger"'), 1)
        self.assertIn('data-shortcut-modifier', html)
        self.assertIn('<kbd>K</kbd>', html)
        self.assertIn('aria-label="Open search (Ctrl+K)"', html)
        self.assertNotIn('id="globalSearchInput"', html)

        form_match = re.search(r'<form[^>]*id="logoutForm"[^>]*>(.*?)</form>', html, re.S)
        self.assertIsNotNone(form_match)
        form_tag = form_match.group(0)
        self.assertIn('method="post"', form_tag)
        self.assertIn(f'action="{reverse("frontend:logout")}"', form_tag)
        self.assertIn('csrfmiddlewaretoken', form_match.group(1))
        self.assertIn('type="button" class="logout-btn"', html)
        self.assertNotIn('type="submit" class="logout-btn"', html)

    def test_palette_has_browse_tabs_prefix_hint_and_search_help(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse('frontend:dashboard')).content.decode()

        self.assertEqual(html.count('role="tablist"'), 1)
        for tab in ['all', 'pages', 'docs', 'products', 'people', 'sales']:
            self.assertIn(f'data-search-tab="{tab}"', html)
        self.assertEqual(html.count('id="searchDocData"'), 1)
        self.assertEqual(html.count('id="searchPrefixHint"'), 1)
        for token in ['page:', 'doc:', 'product:', 'person:', 'sale:']:
            self.assertIn(f'<code>{token}</code>', html)
        self.assertIn(
            f'href="{reverse("frontend:documentation_topic", args=["search"])}"',
            html,
        )
        self.assertIn('Search pages, docs, products, people, sales...', html)

    def test_anonymous_page_renders_no_logout_dialog(self):
        html = self.client.get(reverse('frontend:login')).content.decode()
        self.assertEqual(html.count('id="logoutDialog"'), 0)
        self.assertEqual(html.count('id="searchPalette"'), 0)
        self.assertEqual(html.count('id="preferencesDialog"'), 0)
        self.assertEqual(html.count('id="searchPageData"'), 0)
        self.assertEqual(html.count('aria-modal="true"'), 0)
