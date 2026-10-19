"""Shared parser and registries for the global search palette.

The palette sends the raw query string to ``frontend:api_search`` and the view
uses :func:`parse_search_query`, so advanced-prefix handling lives in exactly
one authoritative place (the backend). The registries below describe the real
page destinations and documentation sections that prefixed searches target.
"""

SEARCH_PREFIXES = {
    'page': 'pages',
    'doc': 'docs',
    'product': 'products',
    'person': 'people',
    'sale': 'sales',
}

SEARCH_PROMPTS = {
    'pages': 'Type after page: to search application pages (for example, page:inventory).',
    'docs': 'Type after doc: to search documentation topics (for example, doc:inventory).',
    'products': 'Type a product name or code after product: (for example, product:rice).',
    'people': 'Type a person name or document after person: (for example, person:maria).',
    'sales': 'Type a sale code or customer name after sale: (for example, sale:1042).',
}

# Keep in sync with the page registry rendered into the palette markup
# (``#searchPageData`` in frontend/templates/frontend/base.html).
PAGE_REGISTRY = (
    {'title': 'Dashboard', 'url_name': 'frontend:dashboard', 'icon': 'layout-dashboard',
     'keywords': 'dashboard home overview'},
    {'title': 'Sales', 'url_name': 'frontend:sales_list', 'icon': 'receipt',
     'keywords': 'sales orders history'},
    {'title': 'New Sale', 'url_name': 'frontend:point_of_sale', 'icon': 'credit-card',
     'keywords': 'new sale pos point of sale checkout'},
    {'title': 'Products', 'url_name': 'frontend:products', 'icon': 'package',
     'keywords': 'products catalog items'},
    {'title': 'Inventory', 'url_name': 'frontend:inventory', 'icon': 'boxes',
     'keywords': 'inventory stock'},
    {'title': 'People', 'url_name': 'frontend:people', 'icon': 'users',
     'keywords': 'people customers students teachers staff'},
    {'title': 'Finance', 'url_name': 'frontend:finance', 'icon': 'banknote',
     'keywords': 'finance receivables payments'},
    {'title': 'Reports', 'url_name': 'frontend:reports', 'icon': 'bar-chart-3',
     'keywords': 'reports analytics'},
    {'title': 'Documentation', 'url_name': 'frontend:documentation', 'icon': 'help-circle',
     'keywords': 'documentation help guide manual'},
)

# Documentation portal registry: one entry per real topic page. This is the
# single source of truth for routing (`frontend:documentation_topic`), the
# documentation index cards, the palette's `#searchDocData` island, and `doc:`
# search results. ``template`` values are fixed paths defined here — never
# derived from user input.
DOC_TOPICS = (
    {
        'slug': 'getting-started', 'title': 'Getting Started', 'group': 'help',
        'icon': 'compass', 'template': 'frontend/documentation/topics/getting_started.html',
        'description': 'Sign in, find your way around Quadrum, replay the first-run guide, and set up interface preferences.',
        'keywords': 'getting started accounts registration access sign in first run guide tour navigation daily workflows areas',
    },
    {
        'slug': 'dashboard', 'title': 'Dashboard', 'group': 'help',
        'icon': 'layout-dashboard', 'template': 'frontend/documentation/topics/dashboard.html',
        'description': 'What the overview cards, recent activity, and inventory indicators show — and where the numbers come from.',
        'keywords': 'dashboard overview cards statistics revenue today receivables low stock recent activity',
    },
    {
        'slug': 'products-inventory', 'title': 'Products and Inventory', 'group': 'help',
        'icon': 'boxes', 'template': 'frontend/documentation/topics/products_inventory.html',
        'description': 'Product fields, stock values and thresholds, and how catalog and inventory adjustments work.',
        'keywords': 'products inventory stock categories minimum stock adjustments movements codes catalog',
    },
    {
        'slug': 'sales-pos', 'title': 'Sales and Point of Sale', 'group': 'help',
        'icon': 'receipt', 'template': 'frontend/documentation/topics/sales_pos.html',
        'description': 'Recording a sale at the point of sale: cart, payment methods, finalization, and safe retries.',
        'keywords': 'sales point of sale pos cart checkout payment methods finalize idempotency receipt history',
    },
    {
        'slug': 'people', 'title': 'People and Customers', 'group': 'help',
        'icon': 'users', 'template': 'frontend/documentation/topics/people.html',
        'description': 'Student, teacher, staff, and visitor records — fields, filters, balances, and lookup.',
        'keywords': 'people customers students teachers staff visitors records registration balance lookup search',
    },
    {
        'slug': 'finance', 'title': 'Finance and Receivables', 'group': 'help',
        'icon': 'banknote', 'template': 'frontend/documentation/topics/finance.html',
        'description': 'Accounts receivable states, registering payments, cancellation rules, and monetary handling.',
        'keywords': 'finance receivables payments pending partial paid overdue cancelled balance due date on account',
    },
    {
        'slug': 'preferences-troubleshooting', 'title': 'Preferences and Troubleshooting', 'group': 'help',
        'icon': 'sliders-horizontal', 'template': 'frontend/documentation/topics/preferences_troubleshooting.html',
        'description': 'The preferences that actually exist and verified fixes for common situations.',
        'keywords': 'preferences theme contrast density corners sidebar text size motion troubleshooting session errors',
    },
    {
        'slug': 'search', 'title': 'Search and Advanced Queries', 'group': 'help',
        'icon': 'search', 'template': 'frontend/documentation/topics/search.html',
        'description': 'How global search works and every supported prefix, with real examples.',
        'keywords': 'search syntax prefixes page doc product person sale examples help browse tabs palette shortcut',
    },
    {
        'slug': 'data-models', 'title': 'Data Models and Business Rules', 'group': 'developer',
        'icon': 'database', 'template': 'frontend/documentation/topics/data_models.html',
        'description': 'A compact map of the entities and the invariants the application enforces.',
        'keywords': 'data model entities relationships invariants database schema developer architecture',
    },
    {
        'slug': 'api', 'title': 'API Reference', 'group': 'developer',
        'icon': 'code', 'template': 'frontend/documentation/topics/api.html',
        'description': 'POS and search JSON endpoints: authentication, CSRF, request payloads, and error responses.',
        'keywords': 'api endpoints pos calculate finalize search json developer reference csrf errors authentication',
    },
)

DOC_GROUP_LABELS = (
    ('help', 'End-user guides'),
    ('developer', 'Developer references'),
)


def doc_topics_by_group():
    """Return ``[{'key', 'label', 'topics'}, ...]`` in registry order."""
    return [
        {'key': key, 'label': label,
         'topics': [topic for topic in DOC_TOPICS if topic['group'] == key]}
        for key, label in DOC_GROUP_LABELS
    ]


def find_doc_topic(slug):
    """Return the registry entry for ``slug`` or ``None``."""
    for topic in DOC_TOPICS:
        if topic['slug'] == slug:
            return topic
    return None


def parse_search_query(raw):
    """Return ``(group_type, term)`` for a raw search query.

    ``group_type`` is one of the registry group names (``pages``, ``docs``,
    ``products``, ``people``, ``sales``) or ``None`` for unprefixed queries.
    Recognized prefixes are case-insensitive and stripped before matching;
    unknown ``word:`` prefixes remain ordinary search text.
    """
    text = (raw or '').strip()
    if ':' in text:
        head, _, rest = text.partition(':')
        group_type = SEARCH_PREFIXES.get(head.strip().lower())
        if group_type:
            return group_type, rest.strip()
    return None, text


def registry_matches(entries, term):
    """Return the registry entries whose title or keywords contain ``term``."""
    wanted = (term or '').lower()
    if not wanted:
        return []
    return [
        entry for entry in entries
        if wanted in entry['title'].lower() or wanted in entry['keywords'].lower()
    ]
