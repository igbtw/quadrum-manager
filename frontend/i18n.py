"""Application language policy and JavaScript-facing translation registry.

Only two languages are supported. ``en`` is the default; ``pt-br`` is the
secondary language. ``LANGUAGE_CHOICES`` is the single allowlist used by the
preference endpoints, the middleware and the model field, so no arbitrary
locale value can ever be persisted or activated.
"""
from django.utils.translation import gettext_lazy as _

# Django language identifiers exposed to users.
LANGUAGE_ENGLISH = 'en'
LANGUAGE_PORTUGUESE_BR = 'pt-br'
DEFAULT_LANGUAGE = LANGUAGE_ENGLISH

# Endonyms are shown as-is in the selector (never translated), matching the
# requirement that the choices read exactly "English" and "Português (Brasil)".
LANGUAGE_CHOICES = (
    (LANGUAGE_ENGLISH, 'English'),
    (LANGUAGE_PORTUGUESE_BR, 'Português (Brasil)'),
)

SUPPORTED_LANGUAGES = frozenset(value for value, _label in LANGUAGE_CHOICES)

# Session key used by anonymous language selection. Matches Django's
# ``LocaleMiddleware`` convention so the standard machinery stays compatible.
SESSION_LANGUAGE_KEY = '_language'


def normalize_language(value):
    """Return a supported language identifier or ``None``.

    The only accepted identifiers are the exact allowlist values; anything
    else (including casing variants, forged locales and control characters)
    is rejected by returning ``None``.
    """
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if value in SUPPORTED_LANGUAGES else None


# ---------------------------------------------------------------------------
# JavaScript user-facing strings.
#
# main.js/language.js read these through the ``#quadrum-i18n`` JSON island
# rendered by ``base.html`` (via Django's ``json_script`` filter, which is
# execution-safe). The values are ``gettext_lazy`` so the catalog of the
# language active for the request is used; the context processor resolves
# them to plain strings before serialization.
# ---------------------------------------------------------------------------
UI_STRINGS = {
    # Destructive confirmation dialog
    'confirm.title': _('Delete record?'),
    'confirm.titleBlocked': _('Cannot delete record'),
    'confirm.note': _('This action cannot be undone.'),
    'confirm.cancel': _('Cancel'),
    'confirm.close': _('Close'),
    'confirm.fallback': _('This action cannot be undone. Continue?'),
    # Preferences / per-page feedback
    'toast.preferences': _('Preferences'),
    'toast.perPageError': _('Could not save records per page.'),
    # Sidebar navigation
    'sidebar.openNavigation': _('Open navigation'),
    'sidebar.closeNavigation': _('Close navigation'),
    'sidebar.expand': _('Expand sidebar'),
    'sidebar.collapse': _('Collapse sidebar'),
    'sidebar.expandTitle': _('Expand sidebar (Ctrl+B)'),
    'sidebar.collapseTitle': _('Collapse sidebar (Ctrl+B)'),
    # Onboarding
    'onboarding.step': _('Step %(current)s of %(total)s'),
    # Theme hints
    'theme.dark': _('Dark'),
    'theme.light': _('Light'),
    'theme.followingSystem': _('Following system setting — currently %(theme)s.'),
    'theme.always': _('Always %(theme)s, regardless of system setting.'),
    # Search palette
    'search.searching': _('Searching…'),
    'search.noResults': _('No results'),
    'search.noResultsFor': _('No results for “%(query)s”.'),
    'search.typeToSearch': _('Type to search Quadrum.'),
    'search.unavailable': _('Search results are unavailable right now.'),
    'search.resultOne': _('%(count)s result'),
    'search.resultMany': _('%(count)s results'),
    'search.openShortcut': _('Open search (%(shortcut)s+K)'),
    'search.titleShortcut': _('Search (%(shortcut)s+K)'),
    'search.placeholder': _('Search pages, products, people, sales…'),
    'search.group.pages': _('Pages'),
    'search.group.docs': _('Documentation'),
    'search.group.products': _('Products'),
    'search.group.people': _('People'),
    'search.group.sales': _('Sales'),
    'search.group.all': _('All'),
    'search.prompt.pages': _('Type after page: to search application pages (for example, page:inventory).'),
    'search.prompt.docs': _('Type after doc: to search documentation topics (for example, doc:inventory).'),
    'search.prompt.products': _('Type a product name or code after product: (for example, product:rice).'),
    'search.prompt.people': _('Type a person name or document after person: (for example, person:maria).'),
    'search.prompt.sales': _('Type a sale code or customer name after sale: (for example, sale:1042).'),
    # Clipboard feedback
    'copy.copied': _('Copied'),
    'copy.failed': _('Copy failed'),
    'copy.unavailable': _('Unable to copy to clipboard'),
    'copy.code': _('Code %(code)s copied'),
    # Charts
    'chart.title': _('Chart'),
    'chart.sales': _('Sales'),
    'chart.revenue': _('Revenue'),
    'chart.units': _('Units'),
    'chart.previousPeriod': _('Previous period'),
    'chart.revenueTooltip': _('Revenue (%(label)s): %(amount)s'),
    'chart.previousTooltip': _('Previous (%(label)s): %(amount)s'),
    'chart.unitsTooltipOne': _('Units: %(units)s · %(count)s transaction'),
    'chart.unitsTooltipMany': _('Units: %(units)s · %(count)s transactions'),
    'chart.paymentTooltipOne': _('%(amount)s · %(count)s sale · %(share)s of revenue'),
    'chart.paymentTooltipMany': _('%(amount)s · %(count)s sales · %(share)s of revenue'),
    # Point of sale
    'pos.decrease': _('Decrease quantity'),
    'pos.increase': _('Increase quantity'),
    'pos.remove': _('Remove item'),
    'pos.added': _('Added'),
    'pos.addedMessage': _('%(name)s added to cart'),
    'pos.cartCleared': _('Cart cleared'),
    'pos.cartClearedMessage': _('All items removed'),
    'pos.cartEmpty': _('Cart empty'),
    'pos.cartEmptyMessage': _('Add products before finalizing'),
    'pos.paymentMethod': _('Payment method'),
    'pos.selectPayment': _('Select a payment method'),
    'pos.finalized': _('Sale finalized'),
    'pos.finalizedMessage': _('Code: %(code)s'),
    'pos.failed': _('Failed to finalize'),
    'pos.failedRetry': _('Failed to finalize sale.'),
    'pos.insufficientStock': _('Insufficient stock.'),
    'pos.invalidPayment': _('Invalid payment method.'),
    'pos.customerNotFound': _('Customer not found.'),
    'pos.customerRequiredTitle': _('Customer required'),
    'pos.customerRequired': _('Choose a customer for On Account sales.'),
    'common.error': _('Error'),
    'common.notice': _('Notice'),
    # Language switcher
    'language.title': _('Language'),
    'language.updated': _('Language updated.'),
    'language.saveError': _('Could not save the language preference.'),
}
