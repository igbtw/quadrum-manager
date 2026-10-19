"""Template context shared by the application shell."""
from urllib.parse import urlencode

from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme

from .i18n import LANGUAGE_CHOICES, UI_STRINGS
from .listsearch import PAGE_SIZE_OPTIONS, resolve_page_size
from .models import OnboardingProgress
from .search import DOC_TOPICS


def documentation(request):
    """Expose the documentation topic registry to every template.

    ``base.html`` renders the search palette's ``#searchDocData`` island from
    this list, so the palette's instant doc matches always mirror the real
    topic routes.
    """
    return {'doc_topics': DOC_TOPICS}


def preferences(request):
    """Expose the session-backed records-per-page preference.

    The Preferences dialog renders its radios from this value, so the control
    always reflects the page size list views will actually use.
    """
    return {
        'list_page_size': resolve_page_size(request),
        'list_page_size_options': PAGE_SIZE_OPTIONS,
    }


def onboarding(request):
    """Expose whether the signed-in user should see the first-run guide."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {'onboarding_pending': False, 'onboarding_step': 0}
    try:
        progress = user.onboarding
    except OnboardingProgress.DoesNotExist:
        return {'onboarding_pending': False, 'onboarding_step': 0}
    return {
        'onboarding_pending': progress.is_pending,
        'onboarding_step': progress.current_step,
    }


def _language_return_url(request):
    """Current auth URL without an unsafe ``next`` destination.

    The anonymous language selector posts this value back so switching
    languages keeps the login/register route and its query string (including a
    safe ``next``) while never rendering an open redirect.
    """
    next_values = request.GET.getlist('next')
    if not next_values or all(
        url_has_allowed_host_and_scheme(
            value,
            {request.get_host()},
            require_https=request.is_secure(),
        )
        for value in next_values
    ):
        return request.get_full_path()

    pairs = [
        (key, value)
        for key, values in request.GET.lists()
        if key != 'next'
        for value in values
    ]
    query = urlencode(pairs)
    return request.path + (f'?{query}' if query else '')


def i18n(request):
    """Expose the active language and the JavaScript translation dictionary.

    Values are resolved to plain strings here (after middleware activation) so
    Django's ``json_script`` filter can serialize them safely; templates still
    render through gettext directly.
    """
    return {
        'current_language': translation.get_language() or 'en',
        'language_choices': LANGUAGE_CHOICES,
        'ui_strings': {key: str(value) for key, value in UI_STRINGS.items()},
        'language_return_url': _language_return_url(request),
    }
