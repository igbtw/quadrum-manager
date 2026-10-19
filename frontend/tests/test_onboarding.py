import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from frontend.models import OnboardingProgress
from frontend.views import ONBOARDING_TOTAL_STEPS

PASSWORD = 'Verdant!Cup7'


def register_user(client, username='newoperator'):
    return client.post(reverse('frontend:register'), {
        'username': username,
        'password1': PASSWORD,
        'password2': PASSWORD,
    })


class OnboardingPersistenceTests(TestCase):
    """Server-side persistence of the first-run guide state."""

    def test_registration_creates_pending_progress_row(self):
        register_user(self.client)
        progress = OnboardingProgress.objects.get(user__username='newoperator')
        self.assertIsNone(progress.completed_at)
        self.assertIsNone(progress.skipped_at)
        self.assertEqual(progress.current_step, 0)
        self.assertTrue(progress.is_pending)

    def test_existing_user_without_row_is_not_pending(self):
        User.objects.create_user(username='veteran', password=PASSWORD)
        self.client.login(username='veteran', password=PASSWORD)
        resp = self.client.get(reverse('frontend:dashboard'))
        self.assertFalse(resp.context['onboarding_pending'])
        self.assertNotContains(resp, 'id="onboardingDialog"')

    def test_registered_user_sees_guide_after_first_login(self):
        register_user(self.client)
        resp = self.client.post(reverse('frontend:login'), {
            'username': 'newoperator', 'password': PASSWORD,
        })
        self.assertRedirects(resp, reverse('frontend:dashboard'))
        page = self.client.get(reverse('frontend:dashboard'))
        self.assertTrue(page.context['onboarding_pending'])
        self.assertContains(page, 'id="onboardingDialog"')
        self.assertContains(page, 'Getting started')

    def test_completion_persists_across_sessions(self):
        register_user(self.client)
        self.client.login(username='newoperator', password=PASSWORD)
        self.client.post(reverse('frontend:onboarding_complete'))

        fresh_client = Client()
        fresh_client.login(username='newoperator', password=PASSWORD)
        page = fresh_client.get(reverse('frontend:dashboard'))
        self.assertFalse(page.context['onboarding_pending'])
        self.assertNotContains(page, 'id="onboardingDialog"')

    def test_skip_persists_across_sessions(self):
        register_user(self.client)
        self.client.login(username='newoperator', password=PASSWORD)
        self.client.post(reverse('frontend:onboarding_skip'))

        fresh_client = Client()
        fresh_client.login(username='newoperator', password=PASSWORD)
        page = fresh_client.get(reverse('frontend:dashboard'))
        self.assertFalse(page.context['onboarding_pending'])

    def test_guide_state_is_per_user(self):
        register_user(self.client)
        other = User.objects.create_user(username='veteran', password=PASSWORD)
        self.client.login(username='newoperator', password=PASSWORD)
        self.client.post(reverse('frontend:onboarding_complete'))

        client = Client()
        client.force_login(other)
        page = client.get(reverse('frontend:dashboard'))
        self.assertFalse(page.context['onboarding_pending'])

        register_user(Client(), username='secondnew')
        second = User.objects.get(username='secondnew')
        client.force_login(second)
        page = client.get(reverse('frontend:dashboard'))
        self.assertTrue(page.context['onboarding_pending'])

    def test_completion_does_not_change_privileges(self):
        register_user(self.client)
        self.client.login(username='newoperator', password=PASSWORD)
        self.client.post(reverse('frontend:onboarding_complete'))
        user = User.objects.get(username='newoperator')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_step_position_resumes_across_sessions(self):
        register_user(self.client)
        self.client.login(username='newoperator', password=PASSWORD)
        self.client.post(reverse('frontend:onboarding_step'), {'step': 2})

        fresh_client = Client()
        fresh_client.login(username='newoperator', password=PASSWORD)
        page = fresh_client.get(reverse('frontend:dashboard'))
        self.assertEqual(page.context['onboarding_step'], 2)
        self.assertContains(page, 'data-onboarding-current="2"')

    def test_restart_resets_step_position(self):
        register_user(self.client)
        self.client.login(username='newoperator', password=PASSWORD)
        self.client.post(reverse('frontend:onboarding_step'), {'step': 4})
        self.client.post(reverse('frontend:onboarding_restart'))
        progress = OnboardingProgress.objects.get(user__username='newoperator')
        self.assertEqual(progress.current_step, 0)
        page = self.client.get(reverse('frontend:dashboard'))
        self.assertContains(page, 'data-onboarding-current="0"')


class OnboardingEndpointTests(TestCase):
    def setUp(self):
        register_user(self.client)
        self.client.login(username='newoperator', password=PASSWORD)
        self.progress = OnboardingProgress.objects.get(user__username='newoperator')

    def test_complete_endpoint(self):
        resp = self.client.post(reverse('frontend:onboarding_complete'))
        self.assertRedirects(resp, reverse('frontend:dashboard'))
        self.progress.refresh_from_db()
        self.assertIsNotNone(self.progress.completed_at)
        self.assertIsNone(self.progress.skipped_at)
        page = self.client.get(reverse('frontend:dashboard'))
        self.assertNotContains(page, 'id="onboardingDialog"')

    def test_skip_endpoint(self):
        resp = self.client.post(reverse('frontend:onboarding_skip'))
        self.assertRedirects(resp, reverse('frontend:dashboard'))
        self.progress.refresh_from_db()
        self.assertIsNotNone(self.progress.skipped_at)
        self.assertIsNone(self.progress.completed_at)

    def test_restart_endpoint_reopens_completed_guide(self):
        self.client.post(reverse('frontend:onboarding_complete'))
        resp = self.client.post(reverse('frontend:onboarding_restart'))
        self.assertRedirects(resp, reverse('frontend:dashboard'))
        self.progress.refresh_from_db()
        self.assertTrue(self.progress.is_pending)
        page = self.client.get(reverse('frontend:dashboard'))
        self.assertContains(page, 'id="onboardingDialog"')

    def test_restart_endpoint_reopens_skipped_guide(self):
        self.client.post(reverse('frontend:onboarding_skip'))
        self.client.post(reverse('frontend:onboarding_restart'))
        self.progress.refresh_from_db()
        self.assertTrue(self.progress.is_pending)

    def test_restart_returns_to_safe_next(self):
        resp = self.client.post(reverse('frontend:onboarding_restart'), {'next': '/documentation/'})
        self.assertRedirects(resp, reverse('frontend:documentation'))

    def test_step_endpoint_persists_position(self):
        resp = self.client.post(reverse('frontend:onboarding_step'), {'step': 3})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.content), {'step': 3})
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.current_step, 3)
        self.assertTrue(self.progress.is_pending)

    def test_step_endpoint_rejects_invalid_values(self):
        for payload in ({}, {'step': ''}, {'step': 'abc'}, {'step': '-1'},
                        {'step': str(ONBOARDING_TOTAL_STEPS)}):
            resp = self.client.post(reverse('frontend:onboarding_step'), payload)
            self.assertEqual(resp.status_code, 400, payload)
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.current_step, 0)

    def test_step_endpoint_conflicts_when_not_pending(self):
        self.client.post(reverse('frontend:onboarding_complete'))
        resp = self.client.post(reverse('frontend:onboarding_step'), {'step': 1})
        self.assertEqual(resp.status_code, 409)
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.current_step, 0)

    def test_step_endpoint_does_not_create_rows(self):
        user = User.objects.create_user(username='veteran', password=PASSWORD)
        client = Client()
        client.force_login(user)
        resp = client.post(reverse('frontend:onboarding_step'), {'step': 1})
        self.assertEqual(resp.status_code, 409)
        self.assertFalse(OnboardingProgress.objects.filter(user=user).exists())

    def test_step_endpoint_requires_post_and_login(self):
        resp = self.client.get(reverse('frontend:onboarding_step'))
        self.assertEqual(resp.status_code, 405)
        resp = Client().post(reverse('frontend:onboarding_step'), {'step': 1})
        self.assertRedirects(resp, '/login/?next=/onboarding/step/')

    def test_unsafe_next_is_ignored(self):
        resp = self.client.post(
            reverse('frontend:onboarding_complete'),
            {'next': 'https://evil.example.com/phish'},
        )
        self.assertRedirects(resp, reverse('frontend:dashboard'))

    def test_complete_then_skip_keeps_completion(self):
        self.client.post(reverse('frontend:onboarding_complete'))
        self.client.post(reverse('frontend:onboarding_skip'))
        self.progress.refresh_from_db()
        self.assertIsNotNone(self.progress.completed_at)

    def test_get_not_allowed(self):
        for name in ('onboarding_complete', 'onboarding_skip', 'onboarding_restart',
                     'onboarding_step'):
            resp = self.client.get(reverse(f'frontend:{name}'))
            self.assertEqual(resp.status_code, 405, name)

    def test_anonymous_post_redirects_to_login(self):
        client = Client()
        resp = client.post(reverse('frontend:onboarding_complete'))
        self.assertRedirects(resp, '/login/?next=/onboarding/complete/')

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.progress.user)
        for name in ('onboarding_complete', 'onboarding_step'):
            resp = client.post(reverse(f'frontend:{name}'))
            self.assertEqual(resp.status_code, 403, name)

    def test_existing_user_can_restart_and_complete(self):
        user = User.objects.create_user(username='veteran', password=PASSWORD)
        client = Client()
        client.force_login(user)
        resp = client.post(reverse('frontend:onboarding_restart'))
        self.assertRedirects(resp, reverse('frontend:dashboard'))
        progress = OnboardingProgress.objects.get(user=user)
        self.assertTrue(progress.is_pending)
        page = client.get(reverse('frontend:dashboard'))
        self.assertContains(page, 'id="onboardingDialog"')
        client.post(reverse('frontend:onboarding_complete'))
        progress.refresh_from_db()
        self.assertIsNotNone(progress.completed_at)


class OnboardingMarkupTests(TestCase):
    def setUp(self):
        register_user(self.client)
        self.client.login(username='newoperator', password=PASSWORD)

    def test_dialog_lists_all_steps_and_targets(self):
        page = self.client.get(reverse('frontend:dashboard')).content.decode()
        for step_title in ('Dashboard', 'Sales', 'New Sale', 'Products and Inventory', 'People and Finance'):
            self.assertIn(step_title, page)
        self.assertEqual(page.count('class="onboarding-step"'), ONBOARDING_TOTAL_STEPS)
        for route in (
            reverse('frontend:dashboard'),
            reverse('frontend:sales_list'),
            reverse('frontend:point_of_sale'),
            reverse('frontend:inventory'),
            reverse('frontend:finance'),
        ):
            self.assertIn(f'data-onboarding-route="{route}"', page)

    def test_dialog_exposes_step_persistence_hooks(self):
        page = self.client.get(reverse('frontend:dashboard')).content.decode()
        self.assertIn(
            f'data-onboarding-step-url="{reverse("frontend:onboarding_step")}"',
            page,
        )
        self.assertIn('data-onboarding-current="0"', page)

    def test_overlay_uses_dedicated_spotlight_instead_of_blurred_shell(self):
        page = self.client.get(reverse('frontend:dashboard')).content.decode()
        self.assertIn('class="onboarding-overlay', page)
        self.assertIn('id="onboardingSpotlight"', page)
        self.assertNotIn('command-overlay onboarding-overlay', page)

    def test_dialog_actions_and_links(self):
        page = self.client.get(reverse('frontend:dashboard')).content.decode()
        self.assertIn(reverse('frontend:onboarding_skip'), page)
        self.assertIn(reverse('frontend:onboarding_complete'), page)
        self.assertIn(reverse('frontend:documentation'), page)
        self.assertIn('Do this later', page)
        self.assertIn('Finish guide', page)

    def test_guide_not_rendered_on_auth_pages(self):
        client = Client()
        for name in ('frontend:login', 'frontend:register'):
            resp = client.get(reverse(name))
            self.assertNotContains(resp, 'onboardingDialog')

    def test_guide_not_rendered_after_completion_on_other_pages(self):
        self.client.post(reverse('frontend:onboarding_complete'))
        for name in ('frontend:products', 'frontend:inventory', 'frontend:sales_list'):
            resp = self.client.get(reverse(name))
            self.assertNotContains(resp, 'onboardingDialog')


class OnboardingClientArchitectureTests(TestCase):
    """Source-level checks for guide behavior that a browser would verify."""

    def read_asset(self, *parts):
        return (Path(settings.BASE_DIR) / 'static' / Path(*parts)).read_text()

    def test_main_js_persists_steps_with_csrf_and_keepalive(self):
        source = self.read_asset('js', 'main.js')
        for marker in [
            'onboardingState = { isOpen: false, target: null }',
            "getAttribute('data-onboarding-current')",
            "getAttribute('data-onboarding-step-url')",
            'keepalive: true',
            "'X-CSRFToken': csrfInput.value",
            'onboarding-overlay--dim',
            "getElementById('onboardingSpotlight')",
            'saveAndNavigate',
        ]:
            self.assertIn(marker, source)

    def test_js_blocks_global_shortcuts_while_guide_open(self):
        source = self.read_asset('js', 'main.js')
        guard = (
            'if (onboardingState.isOpen) {\n'
            '            e.preventDefault();\n'
            '            return;\n'
            '        }'
        )
        self.assertIn(guard, source)
        self.assertEqual(source.count(guard), 2)

    def test_css_provides_spotlight_dim_and_highlight(self):
        components = self.read_asset('css', 'components.css')
        self.assertIn('box-shadow: 0 0 0 9999px', components)
        self.assertIn('.onboarding-overlay--dim', components)
        self.assertIn('.onboarding-spotlight', components)
        self.assertIn('.nav-item.onboarding-highlight', components)

    def test_square_corner_rule_lives_in_variables(self):
        variables = self.read_asset('css', 'variables.css')
        self.assertIn(':root[data-corners="square"]', variables)
        self.assertIn('border-radius: 0 !important', variables)


class DocumentationPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='operator', password=PASSWORD)

    def test_anonymous_redirected_to_login(self):
        resp = self.client.get(reverse('frontend:documentation'))
        self.assertRedirects(resp, '/login/?next=/documentation/')

    def test_page_renders_for_authenticated_user(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('frontend:documentation'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Documentation')
        self.assertContains(resp, 'End-user guides')

    def test_getting_started_topic_covers_workflows(self):
        self.client.force_login(self.user)
        resp = self.client.get(
            reverse('frontend:documentation_topic', args=['getting-started']),
        )
        self.assertContains(resp, 'Daily workflows')

    def test_page_links_to_operational_areas(self):
        self.client.force_login(self.user)
        page = self.client.get(
            reverse('frontend:documentation_topic', args=['getting-started']),
        ).content.decode()
        for name in ('dashboard', 'sales_list', 'point_of_sale', 'products',
                     'inventory', 'people', 'finance', 'reports'):
            self.assertIn(f'href="{reverse(f"frontend:{name}")}"', page, name)

    def test_page_exposes_replay_action(self):
        self.client.force_login(self.user)
        page = self.client.get(reverse('frontend:documentation')).content.decode()
        self.assertIn(reverse('frontend:onboarding_restart'), page)
        self.assertIn('Show getting started guide', page)

    def test_replay_from_page_shows_guide(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse('frontend:onboarding_restart'),
            {'next': reverse('frontend:documentation')},
        )
        self.assertRedirects(resp, reverse('frontend:documentation'))
        page = self.client.get(reverse('frontend:documentation'))
        self.assertContains(page, 'id="onboardingDialog"')

    def test_page_points_to_repository_docs(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('frontend:documentation'))
        self.assertContains(resp, 'README.md')

    def test_help_control_in_app_shell(self):
        self.client.force_login(self.user)
        page = self.client.get(reverse('frontend:dashboard')).content.decode()
        self.assertIn(reverse('frontend:documentation'), page)
        self.assertIn('aria-label="Help and documentation"', page)

    def test_documentation_in_search_palette(self):
        self.client.force_login(self.user)
        page = self.client.get(reverse('frontend:dashboard')).content.decode()
        self.assertIn('documentation help guide manual', page)


class DashboardNavigationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='operator', password=PASSWORD)
        self.client.force_login(self.user)

    def test_dashboard_actions_target_real_routes(self):
        page = self.client.get(reverse('frontend:dashboard')).content.decode()
        self.assertIn(f'href="{reverse("frontend:reports")}"', page)
        self.assertIn(f'href="{reverse("frontend:sales_list")}"', page)
        self.assertIn(f'href="{reverse("frontend:finance")}"', page)
        self.assertIn(f'href="{reverse("frontend:point_of_sale")}"', page)

    def test_dashboard_has_no_inert_action_links(self):
        page = self.client.get(reverse('frontend:dashboard')).content.decode()
        self.assertNotIn('href="#"', page)
