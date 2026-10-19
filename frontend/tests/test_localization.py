import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import translation

from frontend.i18n import LANGUAGE_CHOICES, normalize_language
from frontend.management.commands.compile_translations import parse_po
from frontend.models import UserProfile


class LanguageModelTests(TestCase):
    def test_profile_is_created_with_english_default(self):
        user = User.objects.create_user(username='language-model', password='test-pass-123')
        profile = UserProfile.objects.get(user=user)

        self.assertEqual(profile.language, 'en')

    def test_only_supported_identifiers_are_normalized(self):
        self.assertEqual(normalize_language('en'), 'en')
        self.assertEqual(normalize_language('pt-br'), 'pt-br')
        for invalid in ['pt', 'pt-BR', 'PT-BR', 'en-us', '', None, 123, 'fr']:
            self.assertIsNone(normalize_language(invalid), msg=repr(invalid))

    def test_choices_are_the_two_user_facing_endonyms(self):
        self.assertEqual(
            LANGUAGE_CHOICES,
            (('en', 'English'), ('pt-br', 'Português (Brasil)')),
        )


class LocalePreferenceMiddlewareTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='language-mw', password='test-pass-123')

    def test_profile_language_wins_over_anonymous_session(self):
        profile = self.user.profile
        profile.language = 'pt-br'
        profile.save(update_fields=['language'])

        session = self.client.session
        session['_language'] = 'en'
        session.save()

        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend:dashboard'))

        self.assertIn('<html lang="pt-br"', response.content.decode())
        self.assertIn('Painel', response.content.decode())

    def test_profile_english_ignores_stale_session_portuguese(self):
        session = self.client.session
        session['_language'] = 'pt-br'
        session.save()

        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend:dashboard'))

        self.assertIn('<html lang="en"', response.content.decode())
        self.assertNotIn('lang="pt-br"', response.content.decode())

    def test_anonymous_session_language_is_used(self):
        session = self.client.session
        session['_language'] = 'pt-br'
        session.save()

        response = self.client.get(reverse('frontend:login'))

        self.assertIn('<html lang="pt-br"', response.content.decode())
        self.assertIn('Entrar', response.content.decode())

    def test_invalid_session_value_falls_back_to_english(self):
        session = self.client.session
        session['_language'] = 'fr'
        session.save()

        response = self.client.get(reverse('frontend:login'))

        self.assertIn('<html lang="en"', response.content.decode())

    def test_authenticated_user_without_profile_never_uses_session(self):
        UserProfile.objects.filter(user=self.user).delete()
        session = self.client.session
        session['_language'] = 'pt-br'
        session.save()

        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend:dashboard'))

        self.assertIn('<html lang="en"', response.content.decode())


class LanguageEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='language-api', password='test-pass-123')
        self.preferences_url = reverse('frontend:preferences_language')
        self.anonymous_url = reverse('frontend:set_language')

    def ajax(self):
        return {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}

    def test_preferences_endpoint_requires_login(self):
        response = self.client.post(self.preferences_url, {'language': 'pt-br'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_preferences_endpoint_rejects_get(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.preferences_url).status_code, 405)

    def test_authenticated_user_saves_language_on_profile_and_session(self):
        self.client.force_login(self.user)
        response = self.client.post(
            self.preferences_url, {'language': 'pt-br'}, **self.ajax()
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'language': 'pt-br'})
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.language, 'pt-br')
        self.assertEqual(self.client.session['_language'], 'pt-br')

    def test_authenticated_user_can_save_english(self):
        self.user.profile.language = 'pt-br'
        self.user.profile.save(update_fields=['language'])
        self.client.force_login(self.user)

        response = self.client.post(
            self.preferences_url, {'language': 'en'}, **self.ajax()
        )

        self.assertEqual(response.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.language, 'en')
        self.assertEqual(self.client.session['_language'], 'en')

    def test_language_save_feedback_uses_the_selected_language(self):
        self.client.force_login(self.user)
        self.client.post(self.preferences_url, {'language': 'pt-br'}, **self.ajax())

        html = self.client.get(reverse('frontend:dashboard')).content.decode()
        self.assertIn('Idioma atualizado.', html)

        self.client.post(self.preferences_url, {'language': 'en'}, **self.ajax())
        html = self.client.get(reverse('frontend:dashboard')).content.decode()
        self.assertIn('Language updated.', html)

    def test_invalid_language_is_rejected_without_changes(self):
        self.client.force_login(self.user)
        for invalid in ['', 'pt', 'pt-BR', 'fr', 'en-us']:
            response = self.client.post(
                self.preferences_url, {'language': invalid}, **self.ajax()
            )
            self.assertEqual(response.status_code, 400, msg=invalid)

        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.language, 'en')
        self.assertNotIn('_language', self.client.session)

    def test_anonymous_switch_is_session_backed(self):
        response = self.client.post(
            self.anonymous_url, {'language': 'pt-br'}, **self.ajax()
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'language': 'pt-br'})
        self.assertEqual(self.client.session['_language'], 'pt-br')

        html = self.client.get(reverse('frontend:login')).content.decode()
        self.assertIn('<html lang="pt-br"', html)

    def test_authenticated_user_cannot_use_anonymous_endpoint(self):
        self.client.force_login(self.user)
        response = self.client.post(
            self.anonymous_url, {'language': 'pt-br'}, **self.ajax()
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.session.get('_language'), None)

    def test_plain_form_redirects_to_safe_next(self):
        response = self.client.post(
            self.anonymous_url,
            {'language': 'pt-br', 'next': reverse('frontend:login')},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('frontend:login'))

    def test_plain_form_rejects_external_next(self):
        response = self.client.post(
            self.anonymous_url,
            {'language': 'pt-br', 'next': 'https://evil.example/steal'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('frontend:login'))

    def test_plain_form_without_next_uses_referer(self):
        referer = reverse('frontend:login')
        response = self.client.post(
            self.anonymous_url,
            {'language': 'pt-br'},
            HTTP_REFERER=referer,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], referer)

    def test_anonymous_selector_preserves_safe_next(self):
        response = self.client.get(
            reverse('frontend:login') + '?next=/sales/'
        )
        html = response.content.decode()

        self.assertIn('name="next" value="/login/?next=/sales/"', html)

    def test_anonymous_selector_drops_unsafe_next_but_keeps_other_parameters(self):
        response = self.client.get(
            reverse('frontend:login')
            + '?next=https://evil.example/steal&theme=dark'
        )
        html = response.content.decode()

        self.assertNotIn('evil.example', html)
        self.assertIn('name="next" value="/login/?theme=dark"', html)

    def test_two_accounts_keep_distinct_languages_in_same_browser(self):
        other = User.objects.create_user(
            username='language-other', password='test-pass-123',
        )
        self.user.profile.language = 'pt-br'
        self.user.profile.save(update_fields=['language'])

        self.client.force_login(self.user)
        self.assertIn(
            '<html lang="pt-br"',
            self.client.get(reverse('frontend:dashboard')).content.decode(),
        )

        self.client.logout()
        self.client.force_login(other)
        self.assertEqual(
            other.profile.language, 'en',
        )
        self.assertIn(
            '<html lang="en"',
            self.client.get(reverse('frontend:dashboard')).content.decode(),
        )

        self.client.logout()
        self.client.force_login(self.user)
        self.assertIn(
            '<html lang="pt-br"',
            self.client.get(reverse('frontend:dashboard')).content.decode(),
        )

    def test_saving_language_preserves_unrelated_preferences_and_onboarding(self):
        from frontend.models import OnboardingProgress

        self.client.force_login(self.user)
        session = self.client.session
        session['per_page'] = 40
        session.save()
        progress = OnboardingProgress.objects.create(user=self.user, current_step=2)
        progress.save()

        response = self.client.post(
            self.preferences_url, {'language': 'pt-br'}, **self.ajax()
        )
        self.assertEqual(response.status_code, 200)

        self.user.profile.refresh_from_db()
        progress.refresh_from_db()
        session = self.client.session
        self.assertEqual(self.user.profile.language, 'pt-br')
        self.assertEqual(progress.current_step, 2)
        self.assertEqual(session['per_page'], 40)
        self.assertEqual(session['_language'], 'pt-br')


class LocalizationRenderingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='language-render', password='test-pass-123')

    def test_portuguese_profile_renders_translated_shell_and_preferences(self):
        profile = self.user.profile
        profile.language = 'pt-br'
        profile.save(update_fields=['language'])
        self.client.force_login(self.user)

        html = self.client.get(reverse('frontend:dashboard')).content.decode()

        self.assertIn('<html lang="pt-br"', html)
        self.assertIn('>Painel<', html)
        self.assertIn('>Preferências<', html)
        self.assertIn('>Vendas<', html)
        self.assertIn('Configurações de interface deste navegador.', html)
        self.assertNotIn('>Dashboard<', html)

    def test_preferences_radio_reflects_the_active_language(self):
        profile = self.user.profile
        profile.language = 'pt-br'
        profile.save(update_fields=['language'])
        self.client.force_login(self.user)

        html = self.client.get(reverse('frontend:dashboard')).content.decode()

        self.assertIn(
            'name="quadrum-language" value="pt-br" class="preference-radio" '
            'data-language-option data-language-url="/preferences/language/" checked',
            html,
        )
        self.assertNotIn(
            'name="quadrum-language" value="en" class="preference-radio" '
            'data-language-option data-language-url="/preferences/language/" checked',
            html,
        )

    def test_javascript_string_island_is_translated(self):
        profile = self.user.profile
        profile.language = 'pt-br'
        profile.save(update_fields=['language'])
        self.client.force_login(self.user)

        html = self.client.get(reverse('frontend:dashboard')).content.decode()
        payload = json.loads(
            html.split('id="quadrum-i18n"', 1)[1].split('>', 1)[1].split('</script>', 1)[0]
        )

        self.assertEqual(payload['confirm.cancel'], 'Cancelar')
        self.assertEqual(payload['language.title'], 'Idioma')
        self.assertEqual(payload['sidebar.expand'], 'Expandir barra lateral')

    def test_documentation_is_translated(self):
        profile = self.user.profile
        profile.language = 'pt-br'
        profile.save(update_fields=['language'])
        self.client.force_login(self.user)

        html = self.client.get(reverse('frontend:documentation')).content.decode()

        self.assertIn('Primeiros Passos', html)
        self.assertIn('Pesquisar tópicos de documentação', html)

    def test_anonymous_login_page_offers_language_selector(self):
        html = self.client.get(reverse('frontend:login')).content.decode()

        self.assertIn('data-language-form', html)
        self.assertIn('name="language"', html)
        self.assertIn('>English</option>', html)
        self.assertIn('>Português (Brasil)</option>', html)

    def test_registration_page_has_language_selector_and_lang_attribute(self):
        html = self.client.get(reverse('frontend:register')).content.decode()

        self.assertIn('<html lang="en"', html)
        self.assertIn('data-language-form', html)
        self.assertIn('>Português (Brasil)</option>', html)

    def test_english_is_the_default_for_new_visitors(self):
        html = self.client.get(reverse('frontend:login')).content.decode()

        self.assertIn('<html lang="en"', html)
        self.assertIn('Sign in', html)

    def test_django_messages_and_shared_dialogs_render_in_portuguese(self):
        from frontend.models import Category

        profile = self.user.profile
        profile.language = 'pt-br'
        profile.save(update_fields=['language'])
        self.client.force_login(self.user)
        category = Category.objects.create(name='Categoria de idioma')

        response = self.client.post(
            reverse('frontend:products'),
            {
                'name': 'Produto de idioma',
                'code': 'LANG-1',
                'category': category.pk,
                'price': '10.00',
                'cost_price': '5.00',
                'stock_quantity': '3',
                'minimum_stock': '1',
                'description': '',
            },
            follow=True,
        )

        self.assertContains(response, 'Produto salvo.')
        self.assertContains(response, 'Excluir registro?')

    def test_form_validation_and_reports_render_in_portuguese(self):
        profile = self.user.profile
        profile.language = 'pt-br'
        profile.save(update_fields=['language'])
        self.client.force_login(self.user)

        invalid_product = self.client.post(reverse('frontend:products'), {})
        self.assertContains(invalid_product, 'Este campo é obrigatório.')
        self.assertContains(invalid_product, 'Nome do produto')

        reports = self.client.get(reverse('frontend:reports'))
        self.assertContains(reports, 'Relatórios')
        self.assertContains(reports, 'Receita Concluída')


class CatalogIntegrityTests(TestCase):
    def test_catalog_compiles_without_fuzzy_or_placeholder_errors(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command('compile_translations', '--check', stdout=out)
        self.assertIn('valid:', out.getvalue())

    def test_every_template_msgid_is_present_in_the_catalog(self):
        import ast
        import glob
        import re

        from django.templatetags import i18n
        from django.template.loader import get_template

        po_path = Path(settings.BASE_DIR) / 'locale' / 'pt_BR' / 'LC_MESSAGES' / 'django.po'
        entries = parse_po(po_path.read_text(encoding='utf-8'), po_path)
        catalog = {entry.msgid for entry in entries if entry.msgid}

        def walk(nodes, found):
            for node in nodes:
                if isinstance(node, i18n.TranslateNode):
                    raw = node.filter_expression.var.var
                    try:
                        found.append(ast.literal_eval(raw))
                    except Exception:
                        found.append(raw.strip("'\""))
                elif isinstance(node, i18n.BlockTranslateNode):
                    found.append(node.render_token_list(node.singular)[0])
                for attr in getattr(node, 'child_nodelists', ()):
                    value = getattr(node, attr, None)
                    if isinstance(value, list):
                        walk(value, found)
                if hasattr(node, 'nodelist'):
                    walk(node.nodelist, found)

        missing = set()
        for path in glob.glob(str(Path(settings.BASE_DIR) / 'frontend' / 'templates' / '**' / '*.html'), recursive=True):
            name = path.split('frontend/templates/', 1)[1]
            template = get_template(name)
            found = []
            walk(template.template.nodelist, found)
            for msgid in found:
                if re.search(r'[A-Za-zÀ-ÿ]', msgid) and msgid not in catalog:
                    missing.add(msgid)

        self.assertEqual(missing, set())

    def test_every_javascript_ui_string_is_in_the_catalog(self):
        from frontend.i18n import UI_STRINGS

        po_path = Path(settings.BASE_DIR) / 'locale' / 'pt_BR' / 'LC_MESSAGES' / 'django.po'
        entries = parse_po(po_path.read_text(encoding='utf-8'), po_path)
        catalog = {entry.msgid for entry in entries if entry.msgid}

        missing = {
            str(value) for value in UI_STRINGS.values()
            if str(value) not in catalog
        }
        self.assertEqual(missing, set())

    def test_every_python_translation_call_is_in_the_catalog(self):
        import ast
        import glob

        po_path = Path(settings.BASE_DIR) / 'locale' / 'pt_BR' / 'LC_MESSAGES' / 'django.po'
        entries = parse_po(po_path.read_text(encoding='utf-8'), po_path)
        catalog = {entry.msgid for entry in entries if entry.msgid}

        functions = {
            '_', 'gettext', 'gettext_lazy', 'gettext_noop',
            'ngettext', 'ngettext_lazy', 'pgettext', 'pgettext_lazy',
        }
        missing = set()
        for path in glob.glob(str(Path(settings.BASE_DIR) / 'frontend' / '*.py')):
            tree = ast.parse(Path(path).read_text(encoding='utf-8'), filename=path)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = func.id if isinstance(func, ast.Name) else getattr(func, 'attr', None)
                if name not in functions or not node.args:
                    continue
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    if first.value and first.value not in catalog:
                        missing.add(first.value)

        self.assertEqual(missing, set())

    def test_every_javascript_fallback_is_in_the_catalog(self):
        import ast
        import re

        po_path = Path(settings.BASE_DIR) / 'locale' / 'pt_BR' / 'LC_MESSAGES' / 'django.po'
        entries = parse_po(po_path.read_text(encoding='utf-8'), po_path)
        catalog = {entry.msgid for entry in entries if entry.msgid}

        main_js = (Path(settings.BASE_DIR) / 'static' / 'js' / 'main.js').read_text()
        token = (
            r"""\bt\(\s*'[^']+'\s*,\s*"""
            r"""('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")\)?"""
        )
        missing = set()
        for match in re.finditer(token, main_js):
            fallback = ast.literal_eval(match.group(1))
            if fallback and fallback not in catalog:
                missing.add(fallback)

        self.assertEqual(missing, set())

    def test_mo_file_exists_and_serves_portuguese(self):
        mo_path = Path(settings.BASE_DIR) / 'locale' / 'pt_BR' / 'LC_MESSAGES' / 'django.mo'
        self.assertTrue(mo_path.exists())

        with translation.override('pt-br'):
            self.assertEqual(translation.gettext('Dashboard'), 'Painel')
            self.assertEqual(
                translation.ngettext('%(total)s result', '%(total)s results', 2)
                % {'total': 2},
                '2 resultados',
            )
