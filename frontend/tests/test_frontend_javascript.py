import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

NODE = shutil.which('node')

MAIN_JS_HARNESS = r"""
const fs = require('fs');
const vm = require('vm');

const noop = function () {};
const element = {
    textContent: JSON.stringify({
        'chart.sales': 'Vendas',
        'onboarding.step': 'Passo %(current)s de %(total)s',
    }),
    classList: { add: noop, remove: noop, toggle: noop, contains: () => false },
    style: {},
    dataset: {},
    setAttribute: noop,
    getAttribute: () => null,
    addEventListener: noop,
    appendChild: noop,
    remove: noop,
    focus: noop,
};
const domReadyCallbacks = [];
const sandbox = {
    console,
    setTimeout,
    clearTimeout,
    requestAnimationFrame: (callback) => callback(),
    document: {
        addEventListener: (name, callback) => {
            if (name === 'DOMContentLoaded') domReadyCallbacks.push(callback);
        },
        getElementById: (id) => (id === 'quadrum-i18n' ? element : null),
        querySelector: () => null,
        querySelectorAll: () => [],
        createElement: () => Object.assign({}, element),
        body: { appendChild: noop, style: {} },
        documentElement: {
            dataset: {},
            style: {},
            setAttribute: noop,
            getAttribute: () => null,
        },
        contains: () => false,
        activeElement: null,
    },
    navigator: {},
    localStorage: { getItem: () => null, setItem: noop, removeItem: noop },
    sessionStorage: { getItem: () => null, setItem: noop, removeItem: noop },
    location: { href: 'http://testserver/' },
    getComputedStyle: () => ({ getPropertyValue: () => '' }),
};
sandbox.window = sandbox;
sandbox.matchMedia = () => null;
sandbox.fetch = () => Promise.reject(new Error('offline'));

vm.createContext(sandbox);
try {
    vm.runInContext(fs.readFileSync(process.env.MAIN_JS, 'utf8'), sandbox, {
        filename: 'static/js/main.js',
    });
} catch (error) {
    console.error('LOAD_ERROR', error.name + ': ' + error.message);
    process.exit(1);
}
if (!sandbox.quadrum || typeof sandbox.quadrum.t !== 'function') {
    console.error('MISSING_QUADRUM_T');
    process.exit(2);
}
try {
    domReadyCallbacks.forEach((callback) => callback());
} catch (error) {
    console.error('INIT_ERROR', error.name + ': ' + error.message);
    process.exit(3);
}
console.log(JSON.stringify({
    initialized: 'ok',
    translated: sandbox.quadrum.t('chart.sales', 'Sales'),
    fallback: sandbox.quadrum.t('missing.key', 'Fallback'),
    interpolated: sandbox.quadrum.t(
        'onboarding.step',
        'Step %(current)s of %(total)s',
        { current: 1, total: 3 }
    ),
}));
"""


PAGE_CHART_HARNESS = r"""
const fs = require('fs');
const vm = require('vm');

const noop = function () {};
const canvas = { getContext: () => ({}) };
const island = { textContent: process.env.I18N_JSON };
const chartData = { textContent: process.env.CHART_JSON };
const elements = {
    'quadrum-i18n': island,
    salesChart: canvas,
    'sales-chart-data': chartData,
};
const charts = [];
const pageReadyCallbacks = [];
function Chart(context, config) { charts.push(config); }
Chart.getChart = () => null;

const sandbox = {
    console,
    setTimeout,
    clearTimeout,
    requestAnimationFrame: (callback) => callback(),
    document: {
        readyState: 'loading',
        addEventListener: (name, callback) => {
            if (name === 'DOMContentLoaded') pageReadyCallbacks.push(callback);
        },
        dispatchEvent: noop,
        getElementById: (id) => elements[id] || null,
        querySelector: () => null,
        querySelectorAll: () => [],
        createElement: () => ({
            classList: { add: noop, remove: noop },
            style: {},
            dataset: {},
            setAttribute: noop,
            appendChild: noop,
        }),
        body: { appendChild: noop, style: {} },
        documentElement: {
            dataset: {},
            style: {},
            setAttribute: noop,
            getAttribute: () => null,
        },
        contains: () => false,
        activeElement: null,
    },
    navigator: {},
    localStorage: { getItem: () => null, setItem: noop, removeItem: noop },
    sessionStorage: { getItem: () => null, setItem: noop, removeItem: noop },
    location: { href: 'http://testserver/' },
    getComputedStyle: () => ({ getPropertyValue: () => '' }),
    lucide: { createIcons: noop },
    Chart,
};
sandbox.window = sandbox;
sandbox.matchMedia = () => null;
sandbox.fetch = () => Promise.reject(new Error('offline'));

vm.createContext(sandbox);
try {
    vm.runInContext(fs.readFileSync(process.env.MAIN_JS, 'utf8'), sandbox, {
        filename: 'static/js/main.js',
    });
    vm.runInContext(process.env.PAGE_SCRIPT, sandbox, {
        filename: 'dashboard-inline.js',
    });
    pageReadyCallbacks.forEach((callback) => callback());
} catch (error) {
    console.error('PAGE_ERROR', error.name + ': ' + error.message);
    process.exit(1);
}
console.log(JSON.stringify(charts.map((chart) => chart.data.datasets[0].label)));
"""


MODAL_FOCUS_HARNESS = r"""
const fs = require('fs');
const vm = require('vm');

class FakeClassList {
    constructor() { this.values = new Set(); }
    add(name) { this.values.add(name); }
    remove(name) { this.values.delete(name); }
    contains(name) { return this.values.has(name); }
    toggle(name, force) {
        if (force === undefined) force = !this.contains(name);
        if (force) this.add(name); else this.remove(name);
        return force;
    }
}

class FakeElement {
    constructor(id) {
        this.id = id || '';
        this.classList = new FakeClassList();
        this.style = {};
        this.dataset = {};
        this.attributes = {};
        this.children = [];
        this.parentElement = null;
        this.listeners = {};
        this.textContent = '';
        this.visible = true;
        this.focusables = [];
        this.content = null;
    }
    setAttribute(name, value) { this.attributes[name] = String(value); }
    getAttribute(name) {
        return Object.prototype.hasOwnProperty.call(this.attributes, name)
            ? this.attributes[name] : null;
    }
    hasAttribute(name) {
        return Object.prototype.hasOwnProperty.call(this.attributes, name);
    }
    removeAttribute(name) { delete this.attributes[name]; }
    appendChild(child) {
        this.children.push(child);
        child.parentElement = this;
        return child;
    }
    append() { Array.from(arguments).forEach((child) => this.appendChild(child)); }
    remove() {}
    addEventListener(name, callback) {
        (this.listeners[name] || (this.listeners[name] = [])).push(callback);
    }
    focus() { document.activeElement = this; this.focused = true; }
    getClientRects() { return this.visible ? [{}] : []; }
    contains(node) {
        if (this === node) return true;
        return this.children.some((child) => child.contains(node));
    }
    querySelector(selector) {
        return selector === '.modal-content' ? this.content : null;
    }
    querySelectorAll() { return this.focusables; }
}

const body = new FakeElement('body');
const main = new FakeElement('main');
const background = new FakeElement('background');
const modal = new FakeElement('test-modal');
const content = new FakeElement('modal-content');
const first = new FakeElement('first-focus');
const last = new FakeElement('last-focus');
const opener = new FakeElement('opener');

modal.classList.add('modal-overlay');
modal.content = content;
content.focusables = [first, last];
modal.appendChild(content);
main.appendChild(background);
main.appendChild(modal);
body.appendChild(main);
body.appendChild(opener);

const elements = { 'test-modal': modal };
const readyCallbacks = [];
const listeners = {};
const document = {
    readyState: 'loading',
    body,
    activeElement: opener,
    documentElement: {
        style: {},
        dataset: {},
        setAttribute: () => {},
        getAttribute: () => null,
    },
    addEventListener: (name, callback) => {
        (listeners[name] || (listeners[name] = [])).push(callback);
    },
    dispatchEvent: (event) => {
        (listeners[event.type] || []).forEach((callback) => callback(event));
    },
    getElementById: (id) => elements[id] || null,
    querySelector: () => null,
    querySelectorAll: (selector) => selector === '.modal-overlay' ? [modal] : [],
    createElement: (tag) => new FakeElement(tag),
    contains: (node) => node === body || body.contains(node),
};

function CustomEvent(type) { this.type = type; }

const sandbox = {
    console,
    setTimeout,
    clearTimeout,
    CustomEvent,
    requestAnimationFrame: (callback) => callback(),
    document,
    navigator: {},
    localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
    sessionStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
    location: { href: 'http://testserver/' },
    getComputedStyle: () => ({ getPropertyValue: () => '' }),
};
sandbox.window = sandbox;
sandbox.matchMedia = () => null;
sandbox.fetch = () => Promise.reject(new Error('offline'));

vm.createContext(sandbox);
try {
    vm.runInContext(fs.readFileSync(process.env.MAIN_JS, 'utf8'), sandbox, {
        filename: 'static/js/main.js',
    });
    (listeners.DOMContentLoaded || []).forEach((callback) => callback());
} catch (error) {
    console.error('LOAD_ERROR', error.name + ': ' + error.message);
    process.exit(1);
}

function keydown(key, shiftKey) {
    const event = {
        key,
        shiftKey: Boolean(shiftKey),
        prevented: false,
        preventDefault() { this.prevented = true; },
    };
    (listeners.keydown || []).forEach((callback) => callback(event));
    return event;
}

const result = {};
document.activeElement = opener;
sandbox.openModal('test-modal');
result.openClass = modal.classList.contains('open');
result.backgroundInert = background.getAttribute('inert') === '';
result.backgroundAria = background.getAttribute('aria-hidden') === 'true';
result.focusedFirst = document.activeElement === first;
result.bodyLocked = body.style.overflow === 'hidden';

sandbox.closeModal('test-modal');
result.closed = !modal.classList.contains('open');
result.backgroundRestored = !background.hasAttribute('inert')
    && !background.hasAttribute('aria-hidden');
result.openerRestored = document.activeElement === opener;
result.bodyUnlocked = body.style.overflow === '';

sandbox.openModal('test-modal');
keydown('Escape');
result.escapeClosed = !modal.classList.contains('open');
result.escapeRestoredOpener = document.activeElement === opener;

sandbox.openModal('test-modal');
document.activeElement = last;
const tabEvent = keydown('Tab');
result.tabTrapped = document.activeElement === first && tabEvent.prevented;
sandbox.closeModal('test-modal');

console.log(JSON.stringify(result));
"""


POS_HARNESS = r"""
const fs = require('fs');
const vm = require('vm');

class FakeClassList {
    constructor() { this.values = new Set(); }
    add(name) { this.values.add(name); }
    remove(name) { this.values.delete(name); }
    contains(name) { return this.values.has(name); }
    toggle(name, force) {
        if (force === undefined) force = !this.contains(name);
        if (force) this.add(name); else this.remove(name);
        return force;
    }
}

class FakeElement {
    constructor(id) {
        this.id = id || '';
        this.className = '';
        this.classList = new FakeClassList();
        this.style = {};
        this.dataset = {};
        this.attributes = {};
        this.children = [];
        this.listeners = {};
        this.textContent = '';
        this.innerHTML = '';
        this.value = '';
        this.checked = false;
        this.disabled = false;
        this.hidden = false;
        this.required = false;
        this.radio = null;
        this.productCards = [];
    }
    setAttribute(name, value) { this.attributes[name] = String(value); }
    getAttribute(name) {
        return Object.prototype.hasOwnProperty.call(this.attributes, name)
            ? this.attributes[name] : null;
    }
    removeAttribute(name) { delete this.attributes[name]; }
    appendChild(child) { this.children.push(child); return child; }
    append() { Array.from(arguments).forEach((child) => this.children.push(child)); }
    addEventListener(name, callback) {
        (this.listeners[name] || (this.listeners[name] = [])).push(callback);
    }
    focus() {}
    blur() {}
    scrollIntoView() {}
    querySelector(selector) {
        if (selector === '.product-card-name') return this.nameElement || null;
        if (selector === 'input[name="payment_method"]') return this.radio;
        return null;
    }
    querySelectorAll(selector) {
        if (selector === '.product-card') return this.productCards;
        return [];
    }
}

function makeElement(id) { return new FakeElement(id); }

const productSearch = makeElement('productSearch');
const productResults = makeElement('product-results');
const customerSelect = makeElement('selected-customer');
const customerHint = makeElement('customer-required-hint');
const cartTableBody = makeElement('cart-table-body');
const cartEmpty = makeElement('cart-empty');
const cartTable = makeElement('cart-table');
const cartSubtotal = makeElement('cart-subtotal');
const cartTotal = makeElement('cart-total');

const cashRadio = makeElement('cash-radio');
cashRadio.value = 'CASH';
const accountRadio = makeElement('account-radio');
accountRadio.value = 'ON_ACCOUNT';
const radios = [cashRadio, accountRadio];
const cashOption = makeElement('cash-option');
cashOption.radio = cashRadio;
const accountOption = makeElement('account-option');
accountOption.radio = accountRadio;
const paymentOptions = [cashOption, accountOption];

const allCategory = makeElement('all-category');
allCategory.dataset.categoryId = '';
const drinksCategory = makeElement('drinks-category');
drinksCategory.dataset.categoryId = '1';
const categoryButtons = [allCategory, drinksCategory];

const productCard = makeElement('product-1');
productCard.dataset.id = '1';
productCard.dataset.price = '10.50';
productCard.dataset.category = '1';
productCard.dataset.name = 'suco natural';
productCard.nameElement = makeElement('product-1-name');
productCard.nameElement.textContent = 'Suco Natural';
productResults.productCards = [productCard];

const elements = {
    productSearch,
    'product-results': productResults,
    'selected-customer': customerSelect,
    'customer-required-hint': customerHint,
    'cart-table-body': cartTableBody,
    'cart-empty': cartEmpty,
    'cart-table': cartTable,
    'cart-subtotal': cartSubtotal,
    'cart-total': cartTotal,
};
const readyCallbacks = [];
const storage = new Map();
const requests = [];
const toasts = [];

if (process.env.STORED_STATE) {
    storage.set('pos_checkout', process.env.STORED_STATE);
}

const document = {
    readyState: 'loading',
    cookie: 'csrftoken=test-token',
    documentElement: { lang: process.env.LANG_CODE || 'pt-br' },
    addEventListener: (name, callback) => {
        if (name === 'DOMContentLoaded') readyCallbacks.push(callback);
    },
    getElementById: (id) => elements[id] || null,
    querySelector: (selector) => {
        if (selector === 'input[name="payment_method"]:checked') {
            return radios.find((radio) => radio.checked) || null;
        }
        const match = selector.match(/^input\[name="payment_method"\]\[value="(.+)"\]$/);
        if (match) return radios.find((radio) => radio.value === match[1]) || null;
        return null;
    },
    querySelectorAll: (selector) => {
        if (selector === '.category-btn') return categoryButtons;
        if (selector === 'input[name="payment_method"]') return radios;
        if (selector === '.payment-option') return paymentOptions;
        return [];
    },
    createElement: (tag) => makeElement(tag),
};

const sessionStorage = {
    getItem: (key) => storage.has(key) ? storage.get(key) : null,
    setItem: (key, value) => storage.set(key, String(value)),
    removeItem: (key) => storage.delete(key),
};

function translate(key, fallback, params) {
    let message = fallback;
    if (params) {
        Object.keys(params).forEach((name) => {
            message = message.replace('%(name)s', String(params[name]));
        });
    }
    return message;
}

const sandbox = {
    console,
    setTimeout,
    clearTimeout,
    document,
    sessionStorage,
    Intl,
    crypto: { randomUUID: () => 'NEW-KEY' },
    quadrum: {
        t: translate,
        showToast: (title, message, type) => toasts.push({ title, message, type }),
    },
    fetch: (url, options) => {
        const payload = JSON.parse(options.body);
        requests.push(payload);
        return Promise.resolve({
            json: () => Promise.resolve({ success: true, code: 'SALE-1' }),
        });
    },
};
sandbox.window = sandbox;

vm.createContext(sandbox);

(async function () {
    try {
        vm.runInContext(process.env.POS_SCRIPT, sandbox, {
            filename: 'point-of-sale-inline.js',
        });
        readyCallbacks.forEach((callback) => callback());
    } catch (error) {
        console.error('POS_ERROR', error.name + ': ' + error.message);
        process.exit(1);
    }

    const mode = process.env.MODE;
    if (mode === 'locale') {
        sandbox.addToCart(1, 'Suco Natural', 10.5);
    } else if (mode === 'clear-empty') {
        sandbox.clearCart();
    } else {
        cashRadio.checked = true;
        if (mode === 'stale') {
            sandbox.addToCart(2, 'Novo', 7.5);
        }
        sandbox.finalizeSale();
        await new Promise((resolve) => setImmediate(resolve));
    }

    console.log(JSON.stringify({
        cartTotal: cartTotal.textContent,
        request: requests[0] || null,
        stored: storage.has('pos_checkout')
            ? JSON.parse(storage.get('pos_checkout')) : null,
        toasts,
    }));
})();
"""


class MainJavaScriptRuntimeTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.main_js = Path(settings.BASE_DIR) / 'static' / 'js' / 'main.js'

    def run_main_js(self):
        result = subprocess.run(
            [NODE, '-e', MAIN_JS_HARNESS],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, 'MAIN_JS': str(self.main_js)},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        self.assertNotIn('LOAD_ERROR', result.stderr)
        return json.loads(result.stdout)

    @unittest.skipUnless(NODE, 'node is not installed')
    def test_page_script_loads_and_exposes_quadrum_translation_helper(self):
        payload = self.run_main_js()

        self.assertEqual(payload['initialized'], 'ok')
        self.assertEqual(payload['translated'], 'Vendas')
        self.assertEqual(payload['fallback'], 'Fallback')
        self.assertEqual(payload['interpolated'], 'Passo 1 de 3')


class DashboardChartInitializationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='chart-regression', password='test-pass-123',
        )
        self.user.profile.language = 'pt-br'
        self.user.profile.save(update_fields=['language'])
        self.client.force_login(self.user)

    @unittest.skipUnless(NODE, 'node is not installed')
    def test_dashboard_chart_initializes_with_translated_label(self):
        html = self.client.get(reverse('frontend:dashboard')).content.decode()
        scripts = re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>', html, re.DOTALL)
        chart_script = next(
            script for script in scripts if 'initSalesChart' in script
        )
        island = re.search(
            r'<script id="quadrum-i18n" type="application/json">(.*?)</script>',
            html,
            re.DOTALL,
        )
        chart_data = re.search(
            r'<script id="sales-chart-data" type="application/json">(.*?)</script>',
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(island)
        self.assertIsNotNone(chart_data)

        result = subprocess.run(
            [NODE, '-e', PAGE_CHART_HARNESS],
            capture_output=True,
            text=True,
            timeout=30,
            env={
                **os.environ,
                'MAIN_JS': str(
                    Path(settings.BASE_DIR) / 'static' / 'js' / 'main.js'
                ),
                'PAGE_SCRIPT': chart_script,
                'I18N_JSON': island.group(1),
                'CHART_JSON': chart_data.group(1),
            },
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        self.assertEqual(json.loads(result.stdout), ['Vendas'])


class ScriptOrderTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base = (
            Path(settings.BASE_DIR) / 'frontend' / 'templates' / 'frontend' / 'base.html'
        ).read_text(encoding='utf-8')

    def test_translation_island_and_main_script_precede_page_scripts(self):
        island = self.base.index('json_script:"quadrum-i18n"')
        main = self.base.index("js/main.js")
        language = self.base.index("js/language.js")
        page_scripts = self.base.index('{% block extra_js %}')

        self.assertLess(island, main)
        self.assertLess(main, language)
        self.assertLess(language, page_scripts)

class ModalFocusRuntimeTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.main_js = Path(settings.BASE_DIR) / 'static' / 'js' / 'main.js'

    @unittest.skipUnless(NODE, 'node is not installed')
    def test_modal_focus_is_trapped_background_is_inert_and_opener_restored(self):
        result = subprocess.run(
            [NODE, '-e', MODAL_FOCUS_HARNESS],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, 'MAIN_JS': str(self.main_js)},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(all(payload.values()), payload)

class PosCheckoutRuntimeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='pos-js', password='test-pass-123',
        )
        self.user.profile.language = 'pt-br'
        self.user.profile.save(update_fields=['language'])
        self.client.force_login(self.user)
        category = self.client.get(
            reverse('frontend:point_of_sale'),
        ).context['categories'].first()
        if category is None:
            from frontend.models import Category
            category = Category.objects.create(name='Bebidas')
        from frontend.models import Product
        Product.objects.create(
            name='Suco Natural', code='SUCO-JS', category=category,
            price='10.50', stock_quantity=20,
        )
        html = self.client.get(reverse('frontend:point_of_sale')).content.decode()
        scripts = re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>', html, re.DOTALL)
        self.script = next(script for script in scripts if 'finalizeSale' in script)

    def run_pos(self, mode, stored=None, lang='pt-br'):
        env = {
            **os.environ,
            'POS_SCRIPT': self.script,
            'MODE': mode,
            'LANG_CODE': lang,
        }
        if stored is not None:
            env['STORED_STATE'] = json.dumps(stored)
        result = subprocess.run(
            [NODE, '-e', POS_HARNESS],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        return json.loads(result.stdout)

    def stored_state(self, key='OLD-KEY', quantity=1):
        return {
            'cart': [{
                'id': 1, 'name': 'Suco Natural', 'price': 10.5,
                'quantity': quantity,
            }],
            'payment_method': 'CASH',
            'customer_id': None,
            'idempotency_key': key,
            'payload': {
                'items': [{'product_id': 1, 'quantity': quantity, 'unit_price': 10.5}],
                'customer_id': None,
                'payment_method': 'CASH',
                'idempotency_key': key,
            },
        }

    @unittest.skipUnless(NODE, 'node is not installed')
    def test_pos_total_uses_raw_price_and_locale_formatting(self):
        payload = self.run_pos('locale')
        self.assertEqual(payload['cartTotal'].replace('\xa0', ' '), 'R$ 10,50')

    @unittest.skipUnless(NODE, 'node is not installed')
    def test_stale_retry_uses_current_cart_and_new_key(self):
        payload = self.run_pos('stale', stored=self.stored_state())
        self.assertNotEqual(payload['request']['idempotency_key'], 'OLD-KEY')
        self.assertEqual(
            [item['product_id'] for item in payload['request']['items']],
            [1, 2],
        )
        self.assertIsNone(payload['stored'])

    @unittest.skipUnless(NODE, 'node is not installed')
    def test_matching_retry_reuses_idempotency_key(self):
        payload = self.run_pos('matching', stored=self.stored_state())
        self.assertEqual(payload['request']['idempotency_key'], 'OLD-KEY')
        self.assertEqual(payload['request']['items'][0]['product_id'], 1)

    @unittest.skipUnless(NODE, 'node is not installed')
    def test_clear_removes_pending_checkout_even_when_cart_is_empty(self):
        stored = self.stored_state()
        stored['cart'] = []
        payload = self.run_pos('clear-empty', stored=stored)
        self.assertIsNone(payload['stored'])
        self.assertIsNone(payload['request'])
