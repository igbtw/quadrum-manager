"""Template context shared by the application shell."""
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
