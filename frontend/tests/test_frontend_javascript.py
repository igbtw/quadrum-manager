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
function Chart(context, config) { charts.push(config); }
Chart.getChart = () => null;

const sandbox = {
    console,
    setTimeout,
    clearTimeout,
    requestAnimationFrame: (callback) => callback(),
    document: {
        addEventListener: noop,
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
} catch (error) {
    console.error('PAGE_ERROR', error.name + ': ' + error.message);
    process.exit(1);
}
console.log(JSON.stringify(charts.map((chart) => chart.data.datasets[0].label)));
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
