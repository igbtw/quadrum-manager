from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User

PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


class RegistrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('frontend:register')

    def payload(self, **overrides):
        data = {
            'username': 'newstudent',
            'password1': 'Verdant!Cup7',
            'password2': 'Verdant!Cup7',
        }
        data.update(overrides)
        return data

    def test_register_route_and_page(self):
        self.assertEqual(self.url, '/register/')
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Create your account')

    def test_registration_success_redirects_to_login(self):
        resp = self.client.post(self.url, self.payload())
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('frontend:login'))

    def test_registration_creates_ordinary_user_with_hashed_password(self):
        self.client.post(self.url, self.payload())
        user = User.objects.get(username='newstudent')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password('Verdant!Cup7'))
        self.assertNotEqual(user.password, 'Verdant!Cup7')

    def test_registration_does_not_authenticate(self):
        self.client.post(self.url, self.payload())
        resp = self.client.get('/dashboard/')
        self.assertRedirects(resp, '/login/?next=/dashboard/')

    def test_registered_account_can_sign_in(self):
        self.client.post(self.url, self.payload())
        resp = self.client.post(reverse('frontend:login'), {
            'username': 'newstudent', 'password': 'Verdant!Cup7',
        })
        self.assertRedirects(resp, reverse('frontend:dashboard'))

    def test_success_message_shown_on_login_page(self):
        resp = self.client.post(self.url, self.payload())
        self.assertEqual(resp.status_code, 302)
        page = self.client.get(reverse('frontend:login'))
        self.assertContains(page, 'Account created')

    def test_password_mismatch_rejected(self):
        resp = self.client.post(self.url, self.payload(password2='Verdant!Cup8'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('password2', resp.context['form'].errors)
        self.assertFalse(User.objects.filter(username='newstudent').exists())

    def test_duplicate_username_rejected(self):
        User.objects.create_user(username='newstudent', password='Verdant!Cup7')
        resp = self.client.post(self.url, self.payload())
        self.assertEqual(resp.status_code, 200)
        self.assertIn('username', resp.context['form'].errors)
        self.assertEqual(User.objects.filter(username='newstudent').count(), 1)

    @override_settings(AUTH_PASSWORD_VALIDATORS=PASSWORD_VALIDATORS)
    def test_weak_password_rejected(self):
        resp = self.client.post(self.url, self.payload(password1='12345678', password2='12345678'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('password2', resp.context['form'].errors)
        self.assertFalse(User.objects.filter(username='newstudent').exists())

    def test_registration_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        resp = client.post(self.url, self.payload())
        self.assertEqual(resp.status_code, 403)

    def test_form_exposes_no_privileged_fields(self):
        resp = self.client.get(self.url)
        self.assertNotContains(resp, 'is_staff')
        self.assertNotContains(resp, 'is_superuser')

    def test_authenticated_visitor_redirected_from_register(self):
        user = User.objects.create_user(username='alreadyin', password='Some!Pass9')
        self.client.force_login(user)
        self.assertRedirects(self.client.get(self.url), reverse('frontend:dashboard'))
