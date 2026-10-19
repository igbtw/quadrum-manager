"""Request language resolution for Quadrum.

Language precedence (explicit policy):

1. Authenticated user: ``UserProfile.language`` is authoritative. A stale
   anonymous session selection must never override it.
2. Anonymous user: a validated ``_language`` session value may be used.
3. Otherwise: Django's default language (English).

No database writes happen here. Users without a profile simply fall back to
English until they explicitly save a language preference.
"""
from django.conf import settings
from django.utils import translation

from .i18n import SESSION_LANGUAGE_KEY, normalize_language
from .models import UserProfile


class LocalePreferenceMiddleware:
    """Activate the supported language for the current request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        language = self.resolve_language(request) or settings.LANGUAGE_CODE
        translation.activate(language)
        request.LANGUAGE_CODE = language
        try:
            return self.get_response(request)
        finally:
            # Reset thread-local state; each request resolves its own language.
            translation.deactivate()

    @staticmethod
    def resolve_language(request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            try:
                profile = user.profile
            except UserProfile.DoesNotExist:
                profile = None
            if profile is not None:
                return normalize_language(profile.language)
            # Authenticated without a profile: authoritative default is
            # English, never a leftover anonymous session choice.
            return None
        session = getattr(request, 'session', None)
        if session is not None:
            return normalize_language(session.get(SESSION_LANGUAGE_KEY))
        return None
