"""Small helpers shared by the list pages' search, filters, and pagination.

Each list view keeps its own queryset and filter semantics; this module only
holds the pieces that must behave identically everywhere: query normalization,
date parsing, the session-backed page-size preference, sorted-order
allowlists, and bookmark-safe querystring building.
"""
from datetime import date
from urllib.parse import urlencode

from django.core.paginator import Paginator

PAGE_SIZE_OPTIONS = (10, 20, 40)
DEFAULT_PAGE_SIZE = 20
MAX_QUERY_LENGTH = 100
SESSION_PAGE_SIZE_KEY = 'per_page'

# Strict allowlist for Sales sorting: ``sort`` value -> model ordering fields.
# The primary field is followed by ``id`` so ties are deterministic.
SALES_SORT_FIELDS = {
    'created_at': ('created_at', 'id'),
    'total': ('total', 'id'),
    'code': ('code', 'id'),
}
SALES_DEFAULT_SORT = 'created_at'

# Receivables sorting allowlist (``rsort`` -> ordering fields).
RECEIVABLE_SORT_FIELDS = {
    'due_date': ('due_date', 'id'),
    'person': ('person__name', 'id'),
    'amount': ('original_amount', 'id'),
}
RECEIVABLE_DEFAULT_SORT = 'due_date'


def normalize_q(raw, limit=MAX_QUERY_LENGTH):
    """Collapse whitespace and bound the length of a user-supplied query."""
    return ' '.join((raw or '').split())[:limit]


def parse_iso_date(value):
    """Return a ``date`` for an ISO ``YYYY-MM-DD`` string, else ``None``."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def resolve_page_size(request):
    """Return the effective records-per-page value for this session.

    Values are restricted to ``PAGE_SIZE_OPTIONS``; anything else (missing,
    corrupted, out of range) falls back to ``DEFAULT_PAGE_SIZE``.
    """
    try:
        value = int(request.session.get(SESSION_PAGE_SIZE_KEY, DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        value = DEFAULT_PAGE_SIZE
    if value not in PAGE_SIZE_OPTIONS:
        value = DEFAULT_PAGE_SIZE
    return value


def build_querystring(request, only=None, exclude=(), overrides=None):
    """Build a URL query string from the current GET parameters.

    ``page`` is always dropped (pagination links re-add it). ``only`` and
    ``exclude`` limit which of the remaining parameters are kept — handy when
    one page hosts two independent tables — and ``overrides`` appends or
    replaces values (for example the sort toggles on a header link).
    """
    only = set(only) if only is not None else None
    exclude = set(exclude)
    pairs = []
    for key in request.GET:
        if key == 'page' or key in exclude:
            continue
        if only is not None and key not in only:
            continue
        for value in request.GET.getlist(key):
            if value != '':
                pairs.append((key, value))
    for key, value in (overrides or {}).items():
        if value in (None, ''):
            continue
        pairs = [(k, v) for k, v in pairs if k != key]
        pairs.append((key, value))
    return urlencode(pairs)


def sort_state(request, allowlist, default_field, default_dir=None):
    """Validate ``sort``/``dir`` GET parameters against an allowlist.

    Returns ``(sort, direction, order_by)`` where ``order_by`` is a tuple of
    orm fields with the requested direction applied. Invalid values fall back
    to the default field and its default direction (``desc`` for dates and
    amounts, ``asc`` for text).
    """
    sort = request.GET.get('sort') or default_field
    if sort not in allowlist:
        sort = default_field
    fallback_dir = default_dir or ('asc' if sort in ('code', 'person') else 'desc')
    direction = request.GET.get('dir') or fallback_dir
    if direction not in ('asc', 'desc'):
        direction = fallback_dir
    prefix = '' if direction == 'asc' else '-'
    order_by = tuple(f'{prefix}{field}' for field in allowlist[sort])
    return sort, direction, order_by


def sort_headers(request, allowlist, sort, direction, labels,
                 only=None, exclude=(), default_dir=None):
    """Build header metadata for sortable table columns.

    Each entry carries the toggle URL (preserving every other parameter), the
    ``aria-sort`` state for the ``<th>``, and the visible arrow. Clicking the
    active column flips direction; clicking another column uses its default.
    """
    headers = {}
    for field in allowlist:
        active = field == sort
        if active:
            next_dir = 'asc' if direction == 'desc' else 'desc'
        else:
            fallback = default_dir or ('asc' if field in ('code', 'person') else 'desc')
            next_dir = fallback
        url = '?' + build_querystring(
            request,
            only=only,
            exclude=tuple(set(exclude) | {'sort', 'dir'}),
            overrides={'sort': field, 'dir': next_dir},
        )
        headers[field] = {
            'label': labels.get(field, field),
            'url': url,
            'active': active,
            'aria_sort': ('ascending' if direction == 'asc' else 'descending') if active else 'none',
            'arrow': ('▲' if direction == 'asc' else '▼') if active else '',
        }
    return headers


def paginate(request, queryset, per_page, page_param='page'):
    """Return a ``Page`` for ``page_param`` GET param; invalid values degrade safely."""
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get(page_param))
