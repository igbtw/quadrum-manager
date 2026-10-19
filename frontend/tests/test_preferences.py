import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

PREFERENCE_OPTIONS = {
    'quadrum-theme': ['system', 'light', 'dark'],
    'quadrum-accent': ['default', 'blue', 'violet', 'emerald'],
    'quadrum-density': ['comfortable', 'compact'],
    'quadrum-corners': ['square', 'rounded'],
    'quadrum-sidebar': ['expanded', 'icon'],
    'quadrum-text-size': ['small', 'default', 'large'],
    'quadrum-motion': ['system', 'reduced'],
    'quadrum-contrast': ['disabled', 'enabled'],
    'quadrum-confirm': ['enabled', 'disabled'],
    'quadrum-per-page': ['10', '20', '40'],
}

PREFERENCE_DEFAULTS = {
    'quadrum-theme': 'system',
    'quadrum-accent': 'default',
    'quadrum-density': 'comfortable',
    'quadrum-corners': 'square',
    'quadrum-sidebar': 'expanded',
    'quadrum-text-size': 'default',
    'quadrum-motion': 'system',
    'quadrum-contrast': 'disabled',
    'quadrum-confirm': 'enabled',
    'quadrum-per-page': '20',
}

PREFERENCE_COUNT = len(PREFERENCE_OPTIONS)
OPTION_COUNT = sum(len(values) for values in PREFERENCE_OPTIONS.values())

SETTING_LABELS = {
    'prefThemeLabel': 'Theme',
    'prefAccentLabel': 'Accent color',
    'prefDensityLabel': 'Interface density',
    'prefCornersLabel': 'Corner style',
    'prefSidebarLabel': 'Desktop sidebar',
    'prefTextSizeLabel': 'Text size',
    'prefMotionLabel': 'Motion',
    'prefContrastLabel': 'High contrast',
    'prefConfirmLabel': 'Confirm destructive actions',
    'prefPerPageLabel': 'Records per page',
}

OPTION_LABELS = [
    'System', 'Light', 'Dark',
    'Default', 'Blue', 'Violet', 'Emerald',
    'Comfortable', 'Compact',
    'Square', 'Rounded',
    'Expanded', 'Icon-only',
    'Small', 'Large',
    'Reduced',
    'Disabled', 'Enabled',
    '10', '20', '40',
]


class PreferencesMarkupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='prefs-user', password='test-pass-123')

    def get_html(self, url_name):
        return self.client.get(reverse(f'frontend:{url_name}')).content.decode()

    def test_preferences_control_replaces_theme_toggle_on_all_pages(self):
        self.client.force_login(self.user)
        for url_name in ['dashboard', 'inventory', 'reports']:
            html = self.get_html(url_name)
            self.assertEqual(html.count('id="preferencesBtn"'), 1)
            self.assertIn('aria-label="Preferences"', html)
            self.assertIn('aria-haspopup="dialog"', html)
            self.assertIn('aria-controls="preferencesDialog"', html)
            self.assertIn('data-lucide="sliders-horizontal"', html)
            self.assertNotIn('id="themeToggle"', html)
            self.assertNotIn('theme-toggle', html)

    def test_preferences_palette_renders_once_with_all_settings(self):
        self.client.force_login(self.user)
        html = self.get_html('dashboard')

        self.assertEqual(html.count('id="preferencesDialog"'), 1)
        self.assertIn(
            'role="dialog" aria-modal="true" aria-labelledby="preferencesTitle"',
            html,
        )
        self.assertIn('id="preferencesTitle"', html)
        self.assertIn('id="preferencesSearchInput"', html)
        self.assertIn('placeholder="Search preferences..."', html)
        self.assertIn('id="preferencesEmpty"', html)
        self.assertIn('id="preferencesSettings"', html)

        self.assertEqual(
            re.findall(r'<h3 class="preference-group-title">([^<]+)</h3>', html),
            ['Appearance', 'Navigation', 'Accessibility', 'Behavior'],
        )
        self.assertEqual(html.count('data-preference-group'), 4)
        self.assertEqual(html.count('data-preference-row'), PREFERENCE_COUNT)

        for name, values in PREFERENCE_OPTIONS.items():
            self.assertEqual(
                re.findall(rf'name="{name}" value="([^"]+)"', html),
                values,
                msg=f'unexpected options for {name}',
            )

        self.assertEqual(html.count('class="preference-option"'), OPTION_COUNT)
        self.assertEqual(html.count('class="preference-radio"'), OPTION_COUNT)

    def test_per_page_control_is_server_backed_wiring(self):
        self.client.force_login(self.user)
        html = self.get_html('dashboard')

        self.assertIn('data-per-page-url="/preferences/per-page/"', html)
        dialog = re.search(r'<div class="command-overlay preferences-overlay".*?</div>\s*</div>\s*</div>', html, re.S)
        self.assertIsNotNone(dialog)
        self.assertIn('name="csrfmiddlewaretoken"', dialog.group(0))
        self.assertIn('name="quadrum-per-page"', dialog.group(0))
        self.assertIn('id="prefPerPageLabel">Records per page', html)
        self.assertIn('(10 to 40)', html)

    def test_every_setting_is_labelled_and_reflects_its_default(self):
        self.client.force_login(self.user)
        html = self.get_html('dashboard')

        label_ids = re.findall(r'role="radiogroup" aria-labelledby="([^"]+)"', html)
        self.assertEqual(len(label_ids), len(SETTING_LABELS))
        self.assertEqual(len(set(label_ids)), len(SETTING_LABELS))
        for label_id in label_ids:
            self.assertIn(f'id="{label_id}"', html)
            self.assertIn(label_id, SETTING_LABELS)
            self.assertIn(SETTING_LABELS[label_id], html)

        described_ids = re.findall(
            r'role="radiogroup" aria-labelledby="[^"]+" aria-describedby="([^"]+)"',
            html,
        )
        self.assertEqual(len(described_ids), len(SETTING_LABELS))
        self.assertEqual(len(set(described_ids)), len(SETTING_LABELS))
        for described_id in described_ids:
            self.assertIn(f'id="{described_id}"', html)

        for name, default in PREFERENCE_DEFAULTS.items():
            matches = re.findall(
                rf'<input type="radio" name="{name}" value="([^"]+)" '
                rf'class="preference-radio"( checked)?>',
                html,
            )
            checked = [value for value, flag in matches if flag]
            self.assertEqual(checked, [default], msg=f'wrong default for {name}')

        for option in OPTION_LABELS:
            self.assertIn(
                f'<span class="preference-option-content">{option}</span>',
                html,
                msg=f'missing option label {option}',
            )

    def test_search_metadata_covers_the_new_settings(self):
        self.client.force_login(self.user)
        html = self.get_html('dashboard')

        for label in ['Accent color', 'Text size', 'High contrast', 'Corner style',
                      'Confirm destructive actions']:
            self.assertIn(label, html)
        for option in ['Blue', 'Violet', 'Emerald', 'Small', 'Large',
                       'Square', 'Rounded', 'Disabled', 'Enabled']:
            self.assertIn(option, html)
        self.assertEqual(html.count('data-preference-row'), PREFERENCE_COUNT)

    def test_boot_script_applies_visual_preferences_before_paint(self):
        self.client.force_login(self.user)
        html = self.get_html('dashboard')

        self.assertIn("var KEY = 'quadrum.preferences.v1'", html)
        for marker in [
            "textSize: 'default'",
            "accent: 'default'",
            "highContrast: 'disabled'",
            "confirmDestructive: 'enabled'",
            "cornerStyle: 'square'",
            "setAttribute('data-text-size', prefs.textSize)",
            "setAttribute('data-accent', prefs.accent)",
            "'data-contrast',",
            "prefs.highContrast === 'enabled' ? 'high' : 'default'",
            "setAttribute('data-corners', prefs.cornerStyle)",
        ]:
            self.assertIn(marker, html)

    def test_anonymous_login_page_applies_theme_without_preferences_dialog(self):
        html = self.get_html('login')
        self.assertEqual(html.count('id="preferencesBtn"'), 0)
        self.assertEqual(html.count('id="preferencesDialog"'), 0)
        self.assertEqual(html.count('aria-modal="true"'), 0)
        self.assertEqual(html.count('data-preference-row'), 0)
        self.assertNotIn('id="themeToggle"', html)
        self.assertIn("var KEY = 'quadrum.preferences.v1'", html)
        self.assertIn("'data-theme',", html)

    def test_html_defaults_to_square_corners_before_js(self):
        self.client.force_login(self.user)
        self.assertIn('<html lang="en" data-corners="square">', self.get_html('dashboard'))
        anonymous = Client().get(reverse('frontend:login')).content.decode()
        self.assertIn('<html lang="en" data-corners="square">', anonymous)

    def test_corner_script_restores_stored_style_before_paint(self):
        self.client.force_login(self.user)
        html = self.get_html('dashboard')
        self.assertIn("CORNERS = ['square', 'rounded']", html)
        self.assertIn("if (CORNERS.indexOf(stored.cornerStyle) !== -1)", html)
        self.assertIn("setAttribute('data-corners', prefs.cornerStyle)", html)


class DestructiveConfirmationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='confirm-user', password='test-pass-123')

    def get_html(self, url_name):
        return self.client.get(reverse(f'frontend:{url_name}')).content.decode()

    def test_confirmation_preference_defaults_to_enabled(self):
        self.client.force_login(self.user)
        html = self.get_html('dashboard')
        self.assertIn('id="prefConfirmLabel">Confirm destructive actions', html)
        self.assertIn(
            '<input type="radio" name="quadrum-confirm" value="enabled" '
            'class="preference-radio" checked>',
            html,
        )

    def test_sign_out_confirmation_is_independent_of_the_preference(self):
        self.client.force_login(self.user)
        html = self.get_html('dashboard')

        self.assertIn('id="logoutDialog"', html)
        self.assertIn('Sign out?', html)
        form_match = re.search(r'<form[^>]*id="logoutForm"[^>]*>', html)
        self.assertIsNotNone(form_match)
        self.assertNotIn('data-confirm-destructive', form_match.group(0))

        logout_section = re.search(
            r'<form[^>]*id="logoutForm".*?</form>', html, re.S)
        self.assertIsNotNone(logout_section)
        self.assertNotIn('data-confirm-destructive', logout_section.group(0))

    def test_js_only_confirms_forms_marked_destructive(self):
        source = (Path(settings.BASE_DIR) / 'static' / 'js' / 'main.js').read_text()

        self.assertIn("hasAttribute('data-confirm-destructive')", source)
        self.assertIn('function confirmDestructive', source)
        self.assertIn("confirmDestructive !== 'disabled'", source)
        self.assertIn("'quadrum-confirm': 'confirmDestructive'", source)
        self.assertIn("confirmDestructive: 'enabled'", source)

    def test_destructive_markers_stay_scoped_to_record_management(self):
        """Ordinary pages (and users without management access) never expose
        destructive-marked forms; positive coverage lives in
        test_record_management."""
        self.client.force_login(self.user)
        for url_name in ['dashboard', 'products', 'people', 'finance',
                         'inventory', 'sales_list', 'point_of_sale']:
            html = self.get_html(url_name)
            for form_tag in re.findall(r'<form[^>]*>', html):
                self.assertNotIn(
                    'data-confirm-destructive',
                    form_tag,
                    msg=f'unexpected destructive marker in {url_name}: {form_tag}',
                )


class RecordsPerPageEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='perpage-user', password='test-pass-123')
        self.url = reverse('frontend:preferences_per_page')

    def test_login_required(self):
        resp = self.client.post(self.url, {'per_page': '10'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])

    def test_get_is_not_allowed(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_valid_values_are_stored_in_the_session(self):
        self.client.force_login(self.user)
        for value in (10, 20, 40):
            resp = self.client.post(self.url, {'per_page': str(value)})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json(), {'per_page': value})
            self.assertEqual(self.client.session['per_page'], value)

    def test_invalid_values_are_rejected_and_leave_session_untouched(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {'per_page': '10'})
        for raw in ['15', '0', '-10', 'abc', '', '20.5']:
            resp = self.client.post(self.url, {'per_page': raw})
            self.assertEqual(resp.status_code, 400, msg=raw)
            self.assertEqual(resp.json()['error'], 'invalid per_page')
            self.assertEqual(self.client.session['per_page'], 10)

    def test_missing_value_is_rejected(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, 400)

    def test_stored_value_changes_list_page_size(self):
        from frontend.models import Category, Product

        self.client.force_login(self.user)
        category = Category.objects.create(name='Snacks')
        for index in range(15):
            Product.objects.create(
                name=f'Item {index:02d}', code=f'P{index:02d}', category=category,
                price='1.00', stock_quantity=1,
            )
        default_html = self.client.get(reverse('frontend:products')).content.decode()
        self.assertIn('15 results', default_html)

        self.client.post(self.url, {'per_page': '10'})
        html = self.client.get(reverse('frontend:products')).content.decode()
        self.assertIn('Page 1 of 2', html)
        self.assertIn('Page 2 of 2', self.client.get(
            reverse('frontend:products'), {'page': 2}).content.decode())
