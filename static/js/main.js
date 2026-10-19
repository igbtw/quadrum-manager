// Main JS — vanilla frontend

// Preferences (theme, density, motion, text size, accent, contrast, corner
// style, destructive confirmations) — stored per browser in localStorage; the
// desktop sidebar layout keeps its own key (quadrum.sidebar.collapsed) as
// single source of truth.
var PREFS_KEY = 'quadrum.preferences.v1';
var PREF_THEME_VALUES = ['system', 'light', 'dark'];
var PREF_DENSITY_VALUES = ['comfortable', 'compact'];
var PREF_MOTION_VALUES = ['system', 'reduced'];
var PREF_TEXT_SIZE_VALUES = ['small', 'default', 'large'];
var PREF_ACCENT_VALUES = ['default', 'blue', 'violet', 'emerald'];
var PREF_HIGH_CONTRAST_VALUES = ['disabled', 'enabled'];
var PREF_CONFIRM_VALUES = ['enabled', 'disabled'];
var PREF_CORNER_VALUES = ['square', 'rounded'];
var PREF_DEFAULTS = {
    theme: 'system',
    density: 'comfortable',
    motion: 'system',
    textSize: 'default',
    accent: 'default',
    highContrast: 'disabled',
    confirmDestructive: 'enabled',
    cornerStyle: 'square'
};
var PREF_KEY_BY_RADIO_NAME = {
    'quadrum-theme': 'theme',
    'quadrum-density': 'density',
    'quadrum-motion': 'motion',
    'quadrum-text-size': 'textSize',
    'quadrum-accent': 'accent',
    'quadrum-contrast': 'highContrast',
    'quadrum-confirm': 'confirmDestructive',
    'quadrum-corners': 'cornerStyle'
};
var systemThemeQuery = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
var preferencesState = { isOpen: false, opener: null };
var onboardingState = { isOpen: false, target: null };

function readPreferences() {
    var prefs = {
        theme: PREF_DEFAULTS.theme,
        density: PREF_DEFAULTS.density,
        motion: PREF_DEFAULTS.motion,
        textSize: PREF_DEFAULTS.textSize,
        accent: PREF_DEFAULTS.accent,
        highContrast: PREF_DEFAULTS.highContrast,
        confirmDestructive: PREF_DEFAULTS.confirmDestructive,
        cornerStyle: PREF_DEFAULTS.cornerStyle
    };
    var stored = null;
    try {
        var raw = window.localStorage.getItem(PREFS_KEY);
        if (raw) stored = JSON.parse(raw);
    } catch (e) {
        stored = null;
    }
    if (stored && typeof stored === 'object' && !Array.isArray(stored)) {
        if (PREF_THEME_VALUES.indexOf(stored.theme) !== -1) prefs.theme = stored.theme;
        if (PREF_DENSITY_VALUES.indexOf(stored.density) !== -1) prefs.density = stored.density;
        if (PREF_MOTION_VALUES.indexOf(stored.motion) !== -1) prefs.motion = stored.motion;
        if (PREF_TEXT_SIZE_VALUES.indexOf(stored.textSize) !== -1) prefs.textSize = stored.textSize;
        if (PREF_ACCENT_VALUES.indexOf(stored.accent) !== -1) prefs.accent = stored.accent;
        if (PREF_HIGH_CONTRAST_VALUES.indexOf(stored.highContrast) !== -1) {
            prefs.highContrast = stored.highContrast;
        }
        if (PREF_CONFIRM_VALUES.indexOf(stored.confirmDestructive) !== -1) {
            prefs.confirmDestructive = stored.confirmDestructive;
        }
        if (PREF_CORNER_VALUES.indexOf(stored.cornerStyle) !== -1) {
            prefs.cornerStyle = stored.cornerStyle;
        }
    }
    try {
        var legacy = window.localStorage.getItem('theme');
        if (legacy === 'light' || legacy === 'dark') {
            if (!stored || PREF_THEME_VALUES.indexOf(stored.theme) === -1) {
                prefs.theme = legacy;
                writePreferences(prefs);
            }
            window.localStorage.removeItem('theme');
        }
    } catch (e) {}
    return prefs;
}

function writePreferences(prefs) {
    try {
        window.localStorage.setItem(PREFS_KEY, JSON.stringify({
            theme: prefs.theme,
            density: prefs.density,
            motion: prefs.motion,
            textSize: prefs.textSize,
            accent: prefs.accent,
            highContrast: prefs.highContrast,
            confirmDestructive: prefs.confirmDestructive,
            cornerStyle: prefs.cornerStyle
        }));
    } catch (e) {
        // Storage unavailable (private mode / blocked) — keep in-page state only.
    }
}

function savePreference(key, value) {
    var prefs = readPreferences();
    if (key === 'theme' && PREF_THEME_VALUES.indexOf(value) !== -1) {
        prefs.theme = value;
    } else if (key === 'density' && PREF_DENSITY_VALUES.indexOf(value) !== -1) {
        prefs.density = value;
    } else if (key === 'motion' && PREF_MOTION_VALUES.indexOf(value) !== -1) {
        prefs.motion = value;
    } else if (key === 'textSize' && PREF_TEXT_SIZE_VALUES.indexOf(value) !== -1) {
        prefs.textSize = value;
    } else if (key === 'accent' && PREF_ACCENT_VALUES.indexOf(value) !== -1) {
        prefs.accent = value;
    } else if (key === 'highContrast' && PREF_HIGH_CONTRAST_VALUES.indexOf(value) !== -1) {
        prefs.highContrast = value;
    } else if (key === 'confirmDestructive' && PREF_CONFIRM_VALUES.indexOf(value) !== -1) {
        prefs.confirmDestructive = value;
    } else if (key === 'cornerStyle' && PREF_CORNER_VALUES.indexOf(value) !== -1) {
        prefs.cornerStyle = value;
    } else {
        return prefs;
    }
    writePreferences(prefs);
    return prefs;
}

// Destructive-action confirmations. Only forms explicitly marked with
// data-confirm-destructive are intercepted; everything else (including the
// sign-out form, which keeps its own dialog) is untouched.
function shouldConfirmDestructive() {
    return readPreferences().confirmDestructive !== 'disabled';
}

function confirmDestructive(message) {
    if (!shouldConfirmDestructive()) return true;
    if (typeof window.confirm !== 'function') return true;
    return window.confirm(message || 'This action cannot be undone. Continue?');
}

// Destructive confirmations use the shared dialog when present, with the
// native confirm (honoring the confirmDestructive preference) as fallback.
var destructiveConfirmState = { isOpen: false, form: null, opener: null };

function openDestructiveDialog(form, blocked, opener) {
    var overlay = document.getElementById('destructiveConfirmDialog');
    var titleEl = document.getElementById('destructiveConfirmTitle');
    var recordEl = document.getElementById('destructiveConfirmRecord');
    var detailEl = document.getElementById('destructiveConfirmDetail');
    var cancelBtn = document.getElementById('destructiveConfirmCancelBtn');
    var confirmBtn = document.getElementById('destructiveConfirmSubmitBtn');
    if (!overlay || !titleEl || !cancelBtn || !confirmBtn) return false;
    if (destructiveConfirmState.isOpen) return true;

    destructiveConfirmState.isOpen = true;
    destructiveConfirmState.form = form;
    destructiveConfirmState.opener = opener || null;

    titleEl.textContent = form.getAttribute('data-confirm-title') ||
        (blocked ? 'Cannot delete record' : 'Delete record?');
    var record = form.getAttribute('data-confirm-record') || '';
    if (recordEl) {
        recordEl.textContent = record;
        recordEl.hidden = !record;
    }
    if (detailEl) {
        detailEl.textContent = form.getAttribute('data-confirm-detail') ||
            'This action cannot be undone.';
    }
    // Blocked records: the confirm action is gone, only Close remains.
    confirmBtn.hidden = blocked;
    confirmBtn.disabled = false;
    cancelBtn.disabled = false;
    cancelBtn.textContent = blocked ? 'Close' : 'Cancel';

    overlay.classList.add('open');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    requestAnimationFrame(function() {
        if (!destructiveConfirmState.isOpen) return;
        // Focus the safe choice; confirming always takes a deliberate step.
        cancelBtn.focus({ preventScroll: true });
    });
    return true;
}

function closeDestructiveDialog() {
    if (!destructiveConfirmState.isOpen) return;
    var overlay = document.getElementById('destructiveConfirmDialog');
    destructiveConfirmState.isOpen = false;
    destructiveConfirmState.form = null;
    var opener = destructiveConfirmState.opener;
    destructiveConfirmState.opener = null;
    if (opener && document.contains(opener)) opener.focus({ preventScroll: true });
    if (overlay) overlay.classList.remove('open');
    if (overlay) overlay.setAttribute('aria-hidden', 'true');
    if (!document.querySelector('.modal-overlay.open')) document.body.style.overflow = '';
}

function initDestructiveConfirmations() {
    var root = document.documentElement;
    if (root.dataset.destructiveConfirmBound === 'true') return;
    root.dataset.destructiveConfirmBound = 'true';

    var overlay = document.getElementById('destructiveConfirmDialog');
    var cancelBtn = document.getElementById('destructiveConfirmCancelBtn');
    var confirmBtn = document.getElementById('destructiveConfirmSubmitBtn');

    document.addEventListener('submit', function(e) {
        var form = e.target;
        if (!(form instanceof HTMLFormElement)) return;
        if (!form.hasAttribute('data-confirm-destructive')) return;
        var blocked = form.getAttribute('data-confirm-blocked') === 'true';
        if (blocked) {
            // Integrity protection is authoritative server-side; the dialog
            // exists so the refusal is explained instead of silent.
            e.preventDefault();
            e.stopPropagation();
            if (!openDestructiveDialog(form, true, e.submitter)) {
                var detail = form.getAttribute('data-confirm-detail');
                if (detail && typeof window.alert === 'function') window.alert(detail);
            }
            return;
        }
        if (!shouldConfirmDestructive()) return;
        var message = form.getAttribute('data-confirm-destructive');
        if (!overlay) {
            if (!confirmDestructive(message)) {
                e.preventDefault();
                e.stopPropagation();
            }
            return;
        }
        e.preventDefault();
        e.stopPropagation();
        if (!openDestructiveDialog(form, false, e.submitter)) {
            if (confirmDestructive(message)) form.submit();
        }
    }, true);

    if (!overlay || !cancelBtn || !confirmBtn) return;

    cancelBtn.addEventListener('click', closeDestructiveDialog);

    confirmBtn.addEventListener('click', function() {
        if (confirmBtn.disabled) return;
        var form = destructiveConfirmState.form;
        if (!form) {
            closeDestructiveDialog();
            return;
        }
        confirmBtn.disabled = true;
        cancelBtn.disabled = true;
        if (typeof form.submit === 'function') form.submit();
    });

    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) closeDestructiveDialog();
    });

    document.addEventListener('keydown', function(e) {
        if (!destructiveConfirmState.isOpen) return;
        if (e.key === 'Escape') closeDestructiveDialog();
        else trapFocus(e, overlay);
    });
}

function resolveTheme(mode) {
    if (mode !== 'system') return mode;
    return systemThemeQuery && systemThemeQuery.matches ? 'dark' : 'light';
}

function applyPreferences(prefs) {
    document.documentElement.setAttribute('data-theme', resolveTheme(prefs.theme));
    document.documentElement.setAttribute('data-density', prefs.density);
    document.documentElement.setAttribute('data-motion', prefs.motion);
    document.documentElement.setAttribute('data-text-size', prefs.textSize);
    document.documentElement.setAttribute('data-accent', prefs.accent);
    document.documentElement.setAttribute(
        'data-contrast',
        prefs.highContrast === 'enabled' ? 'high' : 'default'
    );
    document.documentElement.setAttribute('data-corners', prefs.cornerStyle);
}

function initTheme() {
    applyPreferences(readPreferences());
}

// List toolbars: selects and date inputs marked js-auto-submit re-run the
// GET form on change so filters apply without an extra click.
function initListToolbars() {
    document.querySelectorAll('.js-auto-submit').forEach(function(control) {
        if (control.dataset.autoSubmitBound === 'true') return;
        control.dataset.autoSubmitBound = 'true';
        control.addEventListener('change', function() {
            var form = control.closest('form');
            if (form) form.submit();
        });
    });
}

// Records per page is session-backed on the server, so this dialog never
// mirrors it in localStorage; changing it posts to the endpoint and reloads.
function savePageSize(value) {
    var overlay = document.getElementById('preferencesDialog');
    if (!overlay) return;
    var url = overlay.getAttribute('data-per-page-url');
    var csrfInput = overlay.querySelector('input[name="csrfmiddlewaretoken"]');
    if (!url || !csrfInput || typeof window.fetch !== 'function') return;
    if (overlay.dataset.perPageSaving === 'true') return;
    overlay.dataset.perPageSaving = 'true';
    window.fetch(url, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': csrfInput.value
        },
        body: 'per_page=' + encodeURIComponent(value)
    }).then(function(response) {
        if (!response.ok) throw new Error('save failed');
        window.location.reload();
    }).catch(function() {
        delete overlay.dataset.perPageSaving;
        if (typeof showToast === 'function') {
            showToast('Preferences', 'Could not save records per page.', 'error');
        }
    });
}

// Compatibility API: flips the explicit theme without a visible header toggle.
function toggleTheme() {
    var prefs = readPreferences();
    var next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    prefs.theme = next;
    writePreferences(prefs);
    applyPreferences(prefs);
    if (preferencesState.isOpen) syncPreferenceControls();
    return next;
}

if (systemThemeQuery) {
    var onSystemThemeChange = function() {
        var prefs = readPreferences();
        if (prefs.theme !== 'system') return;
        applyPreferences(prefs);
        updateThemeHint(prefs);
    };
    if (typeof systemThemeQuery.addEventListener === 'function') {
        systemThemeQuery.addEventListener('change', onSystemThemeChange);
    } else if (typeof systemThemeQuery.addListener === 'function') {
        systemThemeQuery.addListener(onSystemThemeChange);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Initialize theme
    initTheme();

    // Initialize modals
    initModals();
    
    // Initialize filters
    initFilters();

    // Initialize list toolbars (filters that re-run the GET form on change)
    initListToolbars();

    // Initialize notifications
    initNotifications();
    
    // Initialize sidebar (mobile drawer + desktop collapse)
    initSidebar();

    // Initialize sign-out confirmation, search palette, and preferences
    initLogoutDialog();
    initSearchPalette();
    initPreferences();
    initChartExpand();
    initOnboarding();
    initDocsPage();
    initDestructiveConfirmations();
});

function initModals() {
    // Open modal
    window.openModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('open');
            document.body.style.overflow = 'hidden';
        }
    };

    // Close modal
    window.closeModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('open');
            document.body.style.overflow = '';
        }
    };

    // Close on overlay click
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', function(e) {
            if (e.target === this) {
                this.classList.remove('open');
                document.body.style.overflow = '';
            }
        });
    });

    // Close with ESC
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-overlay.open').forEach(modal => {
                modal.classList.remove('open');
            });
            document.body.style.overflow = '';
        }
    });
}

var sidebarState = { lastFocused: null };
var SIDEBAR_COLLAPSE_KEY = 'quadrum.sidebar.collapsed';

function isDrawerMode() {
    return window.matchMedia('(max-width: 1024px)').matches;
}

function readStoredSidebarCollapsed() {
    try {
        return window.localStorage.getItem(SIDEBAR_COLLAPSE_KEY) === '1';
    } catch (e) {
        return false;
    }
}

function storeSidebarCollapsed(collapsed) {
    try {
        window.localStorage.setItem(SIDEBAR_COLLAPSE_KEY, collapsed ? '1' : '0');
    } catch (e) {
        // Storage unavailable (private mode / blocked) — keep in-page state only.
    }
}

function setSidebarOpen(open) {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;

    const overlay = document.getElementById('sidebarOverlay');
    const toggleBtn = document.getElementById('sidebarToggle');
    const wasOpen = sidebar.classList.contains('open');
    const drawer = open && isDrawerMode();

    sidebar.classList.toggle('open', open);
    if (overlay) overlay.classList.toggle('visible', open);
    document.body.classList.toggle('drawer-open', drawer);

    if (toggleBtn) {
        toggleBtn.setAttribute('aria-expanded', String(open));
        toggleBtn.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    }

    if (drawer && !wasOpen) {
        sidebarState.lastFocused = document.activeElement;
        const first = sidebar.querySelector('a[href], button:not([disabled])');
        if (first) first.focus();
    } else if (!open && wasOpen && isDrawerMode() && sidebar.contains(document.activeElement)) {
        if (toggleBtn) toggleBtn.focus();
        else if (sidebarState.lastFocused) sidebarState.lastFocused.focus();
    }
    if (!open) sidebarState.lastFocused = null;
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    setSidebarOpen(!sidebar.classList.contains('open'));
}

function setSidebarCollapsed(collapsed, persist) {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;

    sidebar.classList.toggle('collapsed', collapsed);
    const layout = document.querySelector('.layout');
    if (layout) layout.classList.toggle('collapsed', collapsed);

    const collapseBtn = document.getElementById('sidebarCollapseBtn');
    if (collapseBtn) {
        collapseBtn.classList.toggle('collapsed', collapsed);
        collapseBtn.setAttribute('aria-expanded', String(!collapsed));
        collapseBtn.setAttribute('aria-label', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
        collapseBtn.setAttribute('title', (collapsed ? 'Expand' : 'Collapse') + ' sidebar (Ctrl+B)');
    }

    if (persist !== false) storeSidebarCollapsed(collapsed);
    if (preferencesState.isOpen) syncPreferenceControls();
}

function toggleSidebarCollapse() {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    setSidebarCollapsed(!sidebar.classList.contains('collapsed'));
}

function initSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar || sidebar.dataset.sidebarReady === 'true') return;
    sidebar.dataset.sidebarReady = 'true';

    const overlay = document.getElementById('sidebarOverlay');
    const toggleBtn = document.getElementById('sidebarToggle');
    const collapseBtn = document.getElementById('sidebarCollapseBtn');

    if (toggleBtn) {
        toggleBtn.addEventListener('click', toggleSidebar);
    }

    if (collapseBtn) {
        collapseBtn.addEventListener('click', toggleSidebarCollapse);
    }

    if (overlay) {
        overlay.addEventListener('click', function() {
            setSidebarOpen(false);
        });
    }

    sidebar.querySelectorAll('.nav-item, .sidebar-logo, .sidebar-signin').forEach(function(link) {
        link.addEventListener('click', function() {
            if (isDrawerMode()) setSidebarOpen(false);
        });
    });

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && sidebar.classList.contains('open')) {
            setSidebarOpen(false);
        }
    });

    sidebar.addEventListener('keydown', function(e) {
        if (e.key !== 'Tab' || !isDrawerMode() || !sidebar.classList.contains('open')) return;
        const focusables = sidebar.querySelectorAll('a[href], button:not([disabled])');
        if (!focusables.length) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
        }
    });

    document.addEventListener('keydown', function(e) {
        if (!(e.ctrlKey || e.metaKey) || e.altKey || e.shiftKey) return;
        if (e.key !== 'b' && e.key !== 'B') return;
        if (e.repeat) return;
        if (onboardingState.isOpen) {
            e.preventDefault();
            return;
        }
        if (isDrawerMode()) return;
        const target = e.target;
        if (target && (target.isContentEditable || target.tagName === 'INPUT' ||
                       target.tagName === 'TEXTAREA' || target.tagName === 'SELECT')) return;
        e.preventDefault();
        toggleSidebarCollapse();
    });

    const mobileQuery = window.matchMedia('(max-width: 1024px)');
    const onViewportChange = function() {
        if (!mobileQuery.matches && sidebar.classList.contains('open')) {
            setSidebarOpen(false);
        }
    };
    if (typeof mobileQuery.addEventListener === 'function') {
        mobileQuery.addEventListener('change', onViewportChange);
    } else if (typeof mobileQuery.addListener === 'function') {
        mobileQuery.addListener(onViewportChange);
    }
}

setSidebarCollapsed(readStoredSidebarCollapsed(), false);

var logoutDialogState = { isOpen: false, opener: null };

function getFocusableElements(container) {
    return Array.from(container.querySelectorAll(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), ' +
        'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )).filter(function(el) {
        return el.getClientRects().length > 0;
    });
}

function trapFocus(event, container) {
    if (event.key !== 'Tab') return;
    const focusable = getFocusableElements(container);
    if (!focusable.length) {
        event.preventDefault();
        return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (!container.contains(document.activeElement)) {
        event.preventDefault();
        first.focus();
        return;
    }
    if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
    }
}

function initLogoutDialog() {
    const overlay = document.getElementById('logoutDialog');
    const logoutBtn = document.getElementById('sidebarLogoutBtn');
    const form = document.getElementById('logoutForm');
    if (!overlay || !logoutBtn || !form || overlay.dataset.bound === 'true') return;
    overlay.dataset.bound = 'true';

    const cancelBtn = document.getElementById('logoutCancelBtn');
    const confirmBtn = document.getElementById('logoutConfirmBtn');

    function openLogoutDialog() {
        if (logoutDialogState.isOpen) return;
        logoutDialogState.isOpen = true;
        logoutDialogState.opener = logoutBtn;
        if (typeof setNotificationPanel === 'function') setNotificationPanel(false);
        overlay.classList.add('open');
        overlay.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
        requestAnimationFrame(function() {
            if (logoutDialogState.isOpen && cancelBtn) cancelBtn.focus({ preventScroll: true });
        });
    }

    function closeLogoutDialog() {
        if (!logoutDialogState.isOpen) return;
        logoutDialogState.isOpen = false;
        const opener = logoutDialogState.opener;
        logoutDialogState.opener = null;
        if (opener && document.contains(opener)) opener.focus();
        overlay.classList.remove('open');
        overlay.setAttribute('aria-hidden', 'true');
        if (!document.querySelector('.modal-overlay.open')) document.body.style.overflow = '';
    }

    logoutBtn.addEventListener('click', openLogoutDialog);

    if (cancelBtn) {
        cancelBtn.addEventListener('click', closeLogoutDialog);
    }

    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) closeLogoutDialog();
    });

    if (confirmBtn) {
        confirmBtn.addEventListener('click', function() {
            if (confirmBtn.disabled) return;
            confirmBtn.disabled = true;
            if (cancelBtn) cancelBtn.disabled = true;
            if (typeof form.requestSubmit === 'function') {
                form.requestSubmit();
            } else {
                form.submit();
            }
        });
    }

    document.addEventListener('keydown', function(e) {
        if (!logoutDialogState.isOpen) return;
        if (e.key === 'Escape') closeLogoutDialog();
        else trapFocus(e, overlay);
    });
}

function initOnboarding() {
    const overlay = document.getElementById('onboardingDialog');
    if (!overlay || overlay.dataset.bound === 'true') return;
    overlay.dataset.bound = 'true';

    const panel = overlay.querySelector('.onboarding-panel');
    const spotlight = document.getElementById('onboardingSpotlight');
    const steps = Array.prototype.slice.call(overlay.querySelectorAll('[data-onboarding-step]'));
    if (!panel || steps.length < 2) return;
    const stepUrl = overlay.getAttribute('data-onboarding-step-url');
    const csrfInput = overlay.querySelector('input[name="csrfmiddlewaretoken"]');

    const progress = document.getElementById('onboardingProgress');
    const nav = document.getElementById('onboardingNav');
    const backBtn = document.getElementById('onboardingBackBtn');
    const nextBtn = document.getElementById('onboardingNextBtn');
    const finishForm = document.getElementById('onboardingFinishForm');
    const laterForm = document.getElementById('onboardingLaterForm');
    const navItems = Array.prototype.slice.call(document.querySelectorAll('.nav-item[href]'));

    let current = parseInt(overlay.getAttribute('data-onboarding-current'), 10);
    if (isNaN(current) || current < 0 || current >= steps.length) current = 0;
    let target = null;
    let savePromise = null;
    let frame = 0;

    function routeFor(index) {
        const route = steps[index].getAttribute('data-onboarding-route');
        return route ? new URL(route, window.location.origin).pathname : '';
    }

    function findTarget() {
        const wanted = routeFor(current);
        if (!wanted) return null;
        for (let i = 0; i < navItems.length; i += 1) {
            const link = navItems[i];
            const path = new URL(link.getAttribute('href'), window.location.origin).pathname;
            if (path !== wanted) continue;
            const rect = link.getBoundingClientRect();
            const onScreen = rect.width > 0 && rect.height > 0 &&
                rect.bottom > 0 && rect.right > 0 &&
                rect.top < window.innerHeight && rect.left < window.innerWidth;
            return onScreen ? link : null;
        }
        return null;
    }

    function positionSpotlight() {
        if (!spotlight) return;
        if (!target) {
            spotlight.hidden = true;
            overlay.classList.add('onboarding-overlay--dim');
            return;
        }
        const rect = target.getBoundingClientRect();
        const pad = 6;
        overlay.classList.remove('onboarding-overlay--dim');
        spotlight.hidden = false;
        spotlight.style.left = (rect.left - pad) + 'px';
        spotlight.style.top = (rect.top - pad) + 'px';
        spotlight.style.width = (rect.width + pad * 2) + 'px';
        spotlight.style.height = (rect.height + pad * 2) + 'px';
    }

    function refreshTarget() {
        if (target) target.classList.remove('onboarding-highlight');
        target = findTarget();
        if (target) target.classList.add('onboarding-highlight');
        onboardingState.target = target;
        positionSpotlight();
    }

    function schedulePosition() {
        if (frame) return;
        frame = window.requestAnimationFrame(function() {
            frame = 0;
            positionSpotlight();
        });
    }

    function render(focusPanel) {
        steps.forEach(function(step, index) {
            if (index === current) step.removeAttribute('hidden');
            else step.setAttribute('hidden', '');
        });
        if (progress) {
            progress.textContent = 'Step ' + (current + 1) + ' of ' + steps.length;
            progress.hidden = false;
        }
        if (nav) nav.hidden = false;
        if (backBtn) backBtn.hidden = current === 0;
        if (nextBtn) nextBtn.hidden = current === steps.length - 1;
        if (finishForm) finishForm.hidden = current !== steps.length - 1;
        refreshTarget();
        if (focusPanel) panel.focus({ preventScroll: true });
    }

    function saveStep(index) {
        if (!stepUrl || !csrfInput || typeof window.fetch !== 'function') {
            return Promise.resolve();
        }
        const previous = savePromise || Promise.resolve();
        savePromise = previous.catch(function() {}).then(function() {
            return window.fetch(stepUrl, {
                method: 'POST',
                credentials: 'same-origin',
                keepalive: true,
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': csrfInput.value
                },
                body: 'step=' + encodeURIComponent(index)
            });
        }).catch(function() {});
        return savePromise;
    }

    function saveAndNavigate(href) {
        if (!href) return;
        const go = function() {
            window.location.href = href;
        };
        saveStep(current).then(go, go);
    }

    function targetContainsPoint(x, y) {
        if (!target) return false;
        const rect = target.getBoundingClientRect();
        const pad = 6;
        return x >= rect.left - pad && x <= rect.right + pad &&
            y >= rect.top - pad && y <= rect.bottom + pad;
    }

    function dismissLater() {
        if (!laterForm) return;
        if (typeof laterForm.requestSubmit === 'function') laterForm.requestSubmit();
        else laterForm.submit();
    }

    if (backBtn) {
        backBtn.addEventListener('click', function() {
            if (current > 0) {
                current -= 1;
                saveStep(current);
                render(true);
            }
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener('click', function() {
            if (current < steps.length - 1) {
                current += 1;
                saveStep(current);
                render(true);
            }
        });
    }

    // Guide links navigate only after the latest step is persisted.
    panel.addEventListener('click', function(e) {
        const link = e.target.closest ? e.target.closest('a[href]') : null;
        if (!link || !panel.contains(link)) return;
        e.preventDefault();
        saveAndNavigate(link.getAttribute('href'));
    });

    // The dim layer blocks page interactions; only the spotlight cutout
    // forwards a click to the highlighted destination.
    overlay.addEventListener('click', function(e) {
        if (e.target !== overlay) return;
        if (targetContainsPoint(e.clientX, e.clientY)) {
            saveAndNavigate(target.getAttribute('href'));
        }
    });

    window.addEventListener('resize', schedulePosition);
    window.addEventListener('scroll', schedulePosition, true);

    document.addEventListener('keydown', function(e) {
        if (!onboardingState.isOpen) return;
        if (e.key === 'Escape') dismissLater();
        else trapFocus(e, overlay);
    });

    onboardingState.isOpen = true;
    document.body.style.overflow = 'hidden';
    render(false);
    requestAnimationFrame(function() {
        panel.focus({ preventScroll: true });
    });
}

function updateThemeHint(prefs) {
    var hint = document.getElementById('prefThemeEffective');
    if (!hint) return;
    prefs = prefs || readPreferences();
    var label = resolveTheme(prefs.theme) === 'dark' ? 'Dark' : 'Light';
    if (prefs.theme === 'system') {
        hint.textContent = 'Following system setting — currently ' + label + '.';
    } else {
        hint.textContent = 'Always ' + label + ', regardless of system setting.';
    }
}

function setRadioValue(name, value) {
    var input = document.querySelector(
        'input[name="' + name + '"][value="' + value + '"]');
    if (input) input.checked = true;
}

function syncPreferenceControls() {
    var prefs = readPreferences();
    setRadioValue('quadrum-theme', prefs.theme);
    setRadioValue('quadrum-density', prefs.density);
    setRadioValue('quadrum-motion', prefs.motion);
    setRadioValue('quadrum-text-size', prefs.textSize);
    setRadioValue('quadrum-accent', prefs.accent);
    setRadioValue('quadrum-contrast', prefs.highContrast);
    setRadioValue('quadrum-confirm', prefs.confirmDestructive);
    setRadioValue('quadrum-corners', prefs.cornerStyle);
    setRadioValue('quadrum-sidebar', readStoredSidebarCollapsed() ? 'icon' : 'expanded');
    updateThemeHint(prefs);
}

function filterPreferences(query) {
    var rows = Array.from(document.querySelectorAll('[data-preference-row]'));
    var groups = Array.from(document.querySelectorAll('[data-preference-group]'));
    var empty = document.getElementById('preferencesEmpty');
    var tokens = String(query || '').trim().toLowerCase().split(/\s+/).filter(Boolean);
    var visibleRows = 0;

    rows.forEach(function(row) {
        var group = row.closest('[data-preference-group]');
        var groupTitle = group ? group.querySelector('.preference-group-title') : null;
        var text = ((groupTitle ? groupTitle.textContent : '') + ' ' +
            (row.textContent || '')).toLowerCase();
        var matches = tokens.every(function(token) {
            return text.indexOf(token) !== -1;
        });
        row.hidden = !matches;
        if (matches) visibleRows += 1;
    });

    groups.forEach(function(group) {
        group.hidden = !group.querySelector('[data-preference-row]:not([hidden])');
    });

    if (empty) empty.hidden = visibleRows !== 0;
}

function initPreferences() {
    var overlay = document.getElementById('preferencesDialog');
    var opener = document.getElementById('preferencesBtn');
    var closeBtn = document.getElementById('preferencesCloseBtn');
    var searchInput = document.getElementById('preferencesSearchInput');
    if (!overlay || !opener || overlay.dataset.bound === 'true') return;
    overlay.dataset.bound = 'true';

    function openPreferences() {
        if (preferencesState.isOpen) return;
        document.dispatchEvent(new CustomEvent('quadrum:preferences-open'));
        preferencesState.isOpen = true;
        preferencesState.opener = opener;
        syncPreferenceControls();
        if (searchInput) searchInput.value = '';
        filterPreferences('');
        if (typeof setNotificationPanel === 'function') setNotificationPanel(false);
        if (typeof setSidebarOpen === 'function' && isDrawerMode()) setSidebarOpen(false);
        overlay.classList.add('open');
        overlay.setAttribute('aria-hidden', 'false');
        opener.setAttribute('aria-expanded', 'true');
        document.body.style.overflow = 'hidden';
        requestAnimationFrame(function() {
            if (!preferencesState.isOpen) return;
            var target = searchInput || overlay.querySelector('.preferences-panel') || overlay;
            target.focus({ preventScroll: true });
        });
    }

    function closePreferences() {
        if (!preferencesState.isOpen) return;
        preferencesState.isOpen = false;
        var lastOpener = preferencesState.opener;
        preferencesState.opener = null;
        overlay.classList.remove('open');
        overlay.setAttribute('aria-hidden', 'true');
        opener.setAttribute('aria-expanded', 'false');
        if (searchInput) searchInput.value = '';
        filterPreferences('');
        if (lastOpener && document.contains(lastOpener)) lastOpener.focus();
        if (!document.querySelector('.modal-overlay.open')) document.body.style.overflow = '';
    }

    opener.addEventListener('click', openPreferences);
    if (closeBtn) closeBtn.addEventListener('click', closePreferences);
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) closePreferences();
    });
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            filterPreferences(this.value);
        });
    }
    overlay.addEventListener('change', function(e) {
        var input = e.target;
        if (!(input instanceof HTMLInputElement) || input.type !== 'radio') return;
        if (input.name === 'quadrum-per-page') {
            savePageSize(input.value);
            return;
        }
        if (input.name === 'quadrum-sidebar') {
            setSidebarCollapsed(input.value === 'icon', true);
            return;
        }
        var key = PREF_KEY_BY_RADIO_NAME[input.name];
        if (!key) return;
        var prefs = savePreference(key, input.value);
        applyPreferences(prefs);
        updateThemeHint(prefs);
    });
    document.addEventListener('keydown', function(e) {
        if (!preferencesState.isOpen) return;
        if (e.key === 'Escape') closePreferences();
        else trapFocus(e, overlay);
    });
    document.addEventListener('quadrum:palette-open', closePreferences);
}

var chartExpandState = { isOpen: false, opener: null, area: null, placeholder: null };

/* Expanded chart view: moves the chart's own .chart-area wrapper (and the
   single existing canvas/Chart instance inside it) into a large dialog, so
   data, legends, tooltips, and formatting are preserved and never rebuilt.
   Chart.js keeps its ResizeObserver on .chart-area, so it re-renders at the
   dialog size; the placeholder keeps the card layout stable while expanded. */
function initChartExpand() {
    const overlay = document.getElementById('chartExpandDialog');
    const body = document.getElementById('chartExpandBody');
    const titleText = document.getElementById('chartExpandTitleText');
    const subtitle = document.getElementById('chartExpandSubtitle');
    const caption = document.getElementById('chartExpandCaption');
    const closeBtn = document.getElementById('chartExpandCloseBtn');
    const buttons = Array.prototype.slice.call(document.querySelectorAll('[data-chart-expand]'));
    if (!overlay || !body || !buttons.length || overlay.dataset.bound === 'true') return;
    overlay.dataset.bound = 'true';

    function panelText(panel, selector) {
        if (!panel) return '';
        const el = panel.querySelector(selector);
        return el ? el.textContent.replace(/\s+/g, ' ').trim() : '';
    }

    function resizeChart(area) {
        if (!area || typeof Chart === 'undefined') return;
        const canvas = area.querySelector('canvas');
        const chart = canvas ? Chart.getChart(canvas) : null;
        if (chart) chart.resize();
    }

    function openChartExpand(button) {
        if (chartExpandState.isOpen || typeof Chart === 'undefined') return;
        const canvas = document.getElementById(button.getAttribute('data-chart-expand'));
        if (!canvas || !Chart.getChart(canvas)) return;
        const area = canvas.closest('.chart-area');
        if (!area || !area.parentNode) return;

        const panel = button.closest('.panel');
        const heading = panel ? panel.querySelector('.panel-title') : null;
        let title = '';
        if (heading) {
            const headingClone = heading.cloneNode(true);
            const headingSubtitle = headingClone.querySelector('.panel-subtitle');
            if (headingSubtitle) headingSubtitle.remove();
            title = headingClone.textContent.replace(/\s+/g, ' ').trim();
        }

        chartExpandState.isOpen = true;
        chartExpandState.opener = button;
        chartExpandState.area = area;

        const placeholder = document.createElement('div');
        placeholder.className = 'chart-area chart-area-placeholder';
        placeholder.setAttribute('aria-hidden', 'true');
        area.parentNode.insertBefore(placeholder, area);
        chartExpandState.placeholder = placeholder;
        body.appendChild(area);

        if (titleText) titleText.textContent = title || button.getAttribute('aria-label') || 'Chart';
        if (subtitle) {
            subtitle.textContent = panelText(panel, '.panel-subtitle');
            subtitle.hidden = !subtitle.textContent;
        }
        if (caption) {
            caption.textContent = panelText(panel, '.chart-caption');
            caption.hidden = !caption.textContent;
        }

        if (typeof setNotificationPanel === 'function') setNotificationPanel(false);
        if (typeof setSidebarOpen === 'function' && isDrawerMode()) setSidebarOpen(false);
        overlay.classList.add('open');
        overlay.setAttribute('aria-hidden', 'false');
        button.setAttribute('aria-expanded', 'true');
        document.body.style.overflow = 'hidden';
        resizeChart(area);
        requestAnimationFrame(function() {
            if (chartExpandState.isOpen && closeBtn) closeBtn.focus({ preventScroll: true });
        });
    }

    function closeChartExpand() {
        if (!chartExpandState.isOpen) return;
        chartExpandState.isOpen = false;
        const area = chartExpandState.area;
        const placeholder = chartExpandState.placeholder;
        const opener = chartExpandState.opener;
        chartExpandState.area = null;
        chartExpandState.placeholder = null;
        chartExpandState.opener = null;

        overlay.classList.remove('open');
        overlay.setAttribute('aria-hidden', 'true');
        if (opener) opener.setAttribute('aria-expanded', 'false');

        if (area && placeholder && placeholder.parentNode) {
            placeholder.parentNode.insertBefore(area, placeholder);
            placeholder.remove();
            resizeChart(area);
        }

        if (opener && document.contains(opener) && typeof opener.focus === 'function') {
            opener.focus({ preventScroll: true });
        }
        if (!document.querySelector('.modal-overlay.open, .command-overlay.open')) {
            document.body.style.overflow = '';
        }
    }

    buttons.forEach(function(button) {
        button.addEventListener('click', function() { openChartExpand(button); });
    });
    if (closeBtn) closeBtn.addEventListener('click', closeChartExpand);
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) closeChartExpand();
    });
    document.addEventListener('keydown', function(e) {
        if (!chartExpandState.isOpen) return;
        if (e.key === 'Escape') closeChartExpand();
        else trapFocus(e, overlay);
    });
    document.addEventListener('quadrum:palette-open', closeChartExpand);
}

var searchPaletteState = {
    isOpen: false,
    opener: null,
    items: [],
    activeIndex: -1,
    remoteGroups: [],
    remoteQuery: null,
    requestSeq: 0,
    abortController: null,
    debounceTimer: null,
    pages: [],
    docs: [],
    activeTab: 'all',
    query: null,
    activeKey: null
};

/* Browse-mode hint shown when a record tab has no static destinations. */
var SEARCH_BROWSE_HINTS = {
    products: 'Type a query to search products — for example, product:rice.',
    people: 'Type a query to search people — for example, person:maria.',
    sales: 'Type a query to search sales — for example, sale:1042.'
};

function initSearchPalette() {
    const overlay = document.getElementById('searchPalette');
    const input = document.getElementById('searchPaletteInput');
    const results = document.getElementById('searchResults');
    const status = document.getElementById('searchStatus');
    const panel = overlay ? overlay.querySelector('.command-panel') : null;
    if (!overlay || !input || !results || !panel || overlay.dataset.bound === 'true') return;
    overlay.dataset.bound = 'true';

    const headerTrigger = document.getElementById('globalSearchTrigger');
    const headerForm = document.getElementById('globalSearchForm');
    const pageData = document.getElementById('searchPageData');
    const docData = document.getElementById('searchDocData');
    const tabsRoot = document.getElementById('searchTabs');
    const tabs = tabsRoot ? Array.prototype.slice.call(tabsRoot.querySelectorAll('[data-search-tab]')) : [];
    const tabValues = tabs.map(function(tab) { return tab.dataset.searchTab; });
    const prefixHint = document.getElementById('searchPrefixHint');
    const searchUrl = overlay.dataset.searchUrl;
    const isAuthenticated = !!document.getElementById('logoutForm');
    const shortcutModifier = document.querySelector('[data-shortcut-modifier]');
    const isMacPlatform = /mac/i.test(
        (navigator.userAgentData && navigator.userAgentData.platform) ||
        navigator.platform ||
        ''
    );
    const shortcutLabel = isMacPlatform ? '\u2318' : 'Ctrl';

    if (shortcutModifier) shortcutModifier.textContent = shortcutLabel;
    if (headerTrigger) {
        headerTrigger.setAttribute('aria-label', 'Open search (' + shortcutLabel + '+K)');
        headerTrigger.setAttribute('title', 'Search (' + shortcutLabel + '+K)');
    }

    searchPaletteState.pages = pageData
        ? Array.from(pageData.querySelectorAll('a')).map(function(link) {
            return {
                title: link.textContent.trim(),
                keywords: (link.dataset.keywords || '').toLowerCase(),
                url: link.getAttribute('href'),
                icon: link.dataset.icon || 'file'
            };
        })
        : [];

    searchPaletteState.docs = docData
        ? Array.from(docData.querySelectorAll('a')).map(function(link) {
            return {
                title: link.textContent.trim(),
                keywords: (link.dataset.keywords || '').toLowerCase(),
                url: link.getAttribute('href'),
                icon: link.dataset.icon || 'book-open'
            };
        })
        : [];

    function isTypingTarget(target) {
        if (!target) return false;
        if (target.isContentEditable) return true;
        const tag = target.tagName;
        return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
    }

    function focusPaletteInput() {
        requestAnimationFrame(function() {
            if (!searchPaletteState.isOpen) return;
            input.focus({ preventScroll: true });
            if (input.value) input.select();
        });
    }

    function openPalette(opener) {
        if (searchPaletteState.isOpen) {
            focusPaletteInput();
            return;
        }
        document.dispatchEvent(new CustomEvent('quadrum:palette-open'));
        searchPaletteState.isOpen = true;
        searchPaletteState.opener = opener || document.activeElement;
        searchPaletteState.remoteGroups = [];
        searchPaletteState.remoteQuery = null;
        searchPaletteState.activeIndex = -1;
        searchPaletteState.activeKey = null;
        searchPaletteState.query = null;
        setActiveTab('all');
        if (typeof setNotificationPanel === 'function') setNotificationPanel(false);
        if (typeof setSidebarOpen === 'function' && isDrawerMode()) setSidebarOpen(false);
        overlay.classList.add('open');
        overlay.setAttribute('aria-hidden', 'false');
        input.setAttribute('aria-expanded', 'true');
        document.body.style.overflow = 'hidden';
        input.value = '';
        runSearch('');
        focusPaletteInput();
    }

    function closePalette() {
        if (!searchPaletteState.isOpen) return;
        searchPaletteState.isOpen = false;
        searchPaletteState.requestSeq += 1;
        if (searchPaletteState.debounceTimer) {
            clearTimeout(searchPaletteState.debounceTimer);
            searchPaletteState.debounceTimer = null;
        }
        if (searchPaletteState.abortController) {
            searchPaletteState.abortController.abort();
            searchPaletteState.abortController = null;
        }
        const opener = searchPaletteState.opener;
        searchPaletteState.opener = null;
        if (opener && document.contains(opener) && typeof opener.focus === 'function') {
            opener.focus();
        }
        overlay.classList.remove('open');
        overlay.setAttribute('aria-hidden', 'true');
        input.setAttribute('aria-expanded', 'false');
        input.setAttribute('aria-activedescendant', '');
        if (!document.querySelector('.modal-overlay.open')) document.body.style.overflow = '';
    }

    function setActiveTab(tab) {
        if (tabValues.indexOf(tab) === -1) tab = 'all';
        searchPaletteState.activeTab = tab;
        tabs.forEach(function(button) {
            const selected = button.dataset.searchTab === tab;
            button.setAttribute('aria-selected', String(selected));
            button.setAttribute('tabindex', selected ? '0' : '-1');
        });
    }

    function entryMatches(entry, query) {
        if (!query) return true;
        return entry.title.toLowerCase().includes(query) || entry.keywords.includes(query);
    }

    function resultItems(entries, subtitle) {
        return entries.map(function(entry) {
            return {
                title: entry.title,
                subtitle: subtitle || '',
                url: entry.url,
                icon: entry.icon
            };
        });
    }

    /* Static destinations for Browse mode and instant local matches while a
       remote search is in flight. Tabs never trigger a fetch. */
    function staticGroups(query, tab) {
        const groups = [];
        if (tab === 'all' || tab === 'pages') {
            const items = resultItems(
                searchPaletteState.pages.filter(function(page) { return entryMatches(page, query); })
            );
            if (items.length) groups.push({ label: 'Pages', type: 'pages', items: items });
        }
        if (tab === 'all' || tab === 'docs') {
            const items = resultItems(
                searchPaletteState.docs.filter(function(doc) { return entryMatches(doc, query); }),
                'Documentation'
            );
            if (items.length) groups.push({ label: 'Documentation', type: 'docs', items: items });
        }
        return groups;
    }

    function filterByTab(groups, tab) {
        if (tab === 'all') return groups;
        return groups.filter(function(group) { return group.type === tab; });
    }

    function browseGroups(tab) {
        if (SEARCH_BROWSE_HINTS[tab]) {
            return { groups: [], notice: SEARCH_BROWSE_HINTS[tab] };
        }
        return { groups: staticGroups('', tab), notice: '' };
    }

    /* Re-render for the current query and tab without issuing a request. */
    function renderForTab(tab) {
        const query = searchPaletteState.query || '';
        if (!query) {
            const browse = browseGroups(tab);
            renderGroups(browse.groups, '', browse.notice);
            return;
        }
        const remoteReady = searchPaletteState.remoteQuery === query;
        const base = remoteReady
            ? searchPaletteState.remoteGroups
            : staticGroups(query.toLowerCase(), 'all');
        // While the debounced request is still in flight, say so instead of
        // claiming "No results" for categories only the server can search.
        const pending = !remoteReady && isAuthenticated && query.trim().length >= 2;
        renderGroups(filterByTab(base, tab), query, pending ? 'Searching\u2026' : '');
    }

    function createItem(item, index) {
        const el = document.createElement('div');
        el.className = 'command-item';
        el.id = 'search-option-' + index;
        el.setAttribute('role', 'option');
        el.setAttribute('aria-selected', 'false');

        const iconWrap = document.createElement('span');
        iconWrap.className = 'command-item-icon';
        iconWrap.setAttribute('aria-hidden', 'true');
        const icon = document.createElement('i');
        icon.setAttribute('data-lucide', item.icon || 'file');
        iconWrap.appendChild(icon);

        const text = document.createElement('span');
        text.className = 'command-item-text';
        const title = document.createElement('span');
        title.className = 'command-item-title';
        title.textContent = item.title || '';
        text.appendChild(title);
        if (item.subtitle) {
            const meta = document.createElement('span');
            meta.className = 'command-item-meta';
            meta.textContent = item.subtitle;
            text.appendChild(meta);
        }

        const hint = document.createElement('span');
        hint.className = 'command-item-hint';
        hint.setAttribute('aria-hidden', 'true');
        hint.textContent = '↵';

        el.appendChild(iconWrap);
        el.appendChild(text);
        el.appendChild(hint);

        el.addEventListener('click', function() {
            selectIndex(index);
        });
        el.addEventListener('mouseenter', function() {
            setActive(index, false);
        });
        return el;
    }

    function renderGroups(groups, query, notice) {
        const previousQuery = searchPaletteState.query;
        const previousKey = searchPaletteState.activeKey;
        const previousIndex = searchPaletteState.activeIndex;

        results.textContent = '';
        searchPaletteState.items = [];

        groups.forEach(function(group) {
            const label = document.createElement('div');
            label.className = 'command-group-label';
            label.setAttribute('role', 'presentation');
            label.textContent = group.label;
            results.appendChild(label);
            group.items.forEach(function(item) {
                const index = searchPaletteState.items.length;
                const el = createItem(item, index);
                searchPaletteState.items.push({
                    el: el,
                    url: item.url,
                    key: String(group.type || '') + '|' + String(item.title || '') + '|' + String(item.url || '')
                });
                results.appendChild(el);
            });
        });
        searchPaletteState.query = query;
        if (prefixHint) prefixHint.hidden = !!query;

        if (notice && searchPaletteState.items.length) {
            const note = document.createElement('div');
            note.className = 'command-note';
            note.textContent = notice;
            results.appendChild(note);
        }

        if (!searchPaletteState.items.length) {
            const empty = document.createElement('div');
            empty.className = 'command-empty';
            empty.textContent = notice || (query
                ? 'No results for \u201c' + query + '\u201d.'
                : 'Type to search Quadrum.');
            results.appendChild(empty);
            searchPaletteState.activeIndex = -1;
            searchPaletteState.activeKey = null;
            input.setAttribute('aria-activedescendant', '');
            if (status) status.textContent = 'No results';
        } else {
            if (status) {
                const count = searchPaletteState.items.length;
                status.textContent = count + (count === 1 ? ' result' : ' results');
            }
            let target = -1;
            if (previousQuery === query && previousIndex >= 0) {
                if (previousKey) {
                    target = searchPaletteState.items.findIndex(function(candidate) {
                        return candidate.key === previousKey;
                    });
                }
                if (target < 0) target = Math.min(previousIndex, searchPaletteState.items.length - 1);
            }
            setActive(target >= 0 ? target : 0, false);
        }

        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }
        if (previousQuery !== query) results.scrollTop = 0;
    }

    function setActive(index, scroll) {
        if (!searchPaletteState.items.length) {
            searchPaletteState.activeIndex = -1;
            searchPaletteState.activeKey = null;
            input.setAttribute('aria-activedescendant', '');
            return;
        }
        const count = searchPaletteState.items.length;
        searchPaletteState.activeIndex = ((index % count) + count) % count;
        searchPaletteState.items.forEach(function(item, i) {
            item.el.setAttribute('aria-selected', String(i === searchPaletteState.activeIndex));
        });
        const active = searchPaletteState.items[searchPaletteState.activeIndex];
        searchPaletteState.activeKey = active.key;
        input.setAttribute('aria-activedescendant', active.el.id);
        if (scroll !== false) active.el.scrollIntoView({ block: 'nearest' });
    }

    function selectIndex(index) {
        const item = searchPaletteState.items[index];
        if (!item || !item.url) return;
        window.location.assign(item.url);
    }

    function fetchRemote(query, seq) {
        if (!searchUrl || !window.fetch) return;
        const controller = typeof AbortController === 'function' ? new AbortController() : null;
        searchPaletteState.abortController = controller;
        const options = { headers: { 'Accept': 'application/json' } };
        if (controller) options.signal = controller.signal;

        fetch(searchUrl + '?q=' + encodeURIComponent(query), options)
            .then(function(response) {
                if (!response.ok) throw new Error('HTTP ' + response.status);
                return response.json();
            })
            .then(function(data) {
                if (seq !== searchPaletteState.requestSeq) return;
                searchPaletteState.abortController = null;
                searchPaletteState.remoteGroups = Array.isArray(data.groups) ? data.groups : [];
                searchPaletteState.remoteQuery = query;
                const notice = typeof data.prompt === 'string' ? data.prompt : '';
                renderGroups(
                    filterByTab(searchPaletteState.remoteGroups, searchPaletteState.activeTab),
                    query,
                    notice
                );
            })
            .catch(function(error) {
                if (error.name === 'AbortError') return;
                if (seq !== searchPaletteState.requestSeq) return;
                searchPaletteState.abortController = null;
                searchPaletteState.remoteGroups = [];
                searchPaletteState.remoteQuery = null;
                console.error('Search failed', error);
                renderGroups(
                    filterByTab(staticGroups(query.toLowerCase(), 'all'), searchPaletteState.activeTab),
                    query,
                    'Search results are unavailable right now.'
                );
            });
    }

    function runSearch(rawQuery) {
        const query = rawQuery.trim();
        const normalized = query.toLowerCase();
        searchPaletteState.remoteGroups = [];
        searchPaletteState.remoteQuery = null;
        searchPaletteState.requestSeq += 1;
        const seq = searchPaletteState.requestSeq;
        if (searchPaletteState.debounceTimer) {
            clearTimeout(searchPaletteState.debounceTimer);
            searchPaletteState.debounceTimer = null;
        }
        if (searchPaletteState.abortController) {
            searchPaletteState.abortController.abort();
            searchPaletteState.abortController = null;
        }

        if (!normalized) {
            const browse = browseGroups(searchPaletteState.activeTab);
            renderGroups(browse.groups, '', browse.notice);
            return;
        }

        // Instant local matches while the debounced request is in flight.
        renderGroups(
            filterByTab(staticGroups(normalized, 'all'), searchPaletteState.activeTab),
            query
        );

        if (!isAuthenticated || normalized.length < 2) return;

        searchPaletteState.debounceTimer = setTimeout(function() {
            searchPaletteState.debounceTimer = null;
            fetchRemote(query, seq);
        }, 150);
    }

    tabs.forEach(function(button) {
        button.addEventListener('click', function() {
            setActiveTab(button.dataset.searchTab);
            searchPaletteState.activeIndex = -1;
            searchPaletteState.activeKey = null;
            renderForTab(searchPaletteState.activeTab);
            input.focus({ preventScroll: true });
        });
    });

    if (tabsRoot) {
        tabsRoot.addEventListener('keydown', function(e) {
            if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
            const currentIndex = tabs.indexOf(document.activeElement);
            if (currentIndex === -1) return;
            e.preventDefault();
            const delta = e.key === 'ArrowRight' ? 1 : -1;
            const next = tabs[(currentIndex + delta + tabs.length) % tabs.length];
            next.focus();
        });
    }

    input.addEventListener('input', function() {
        runSearch(input.value);
    });

    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) closePalette();
    });

    if (headerTrigger) {
        headerTrigger.addEventListener('click', function() {
            openPalette(headerTrigger);
        });
    }

    if (headerForm) {
        headerForm.addEventListener('submit', function(e) {
            e.preventDefault();
            openPalette(headerTrigger || document.activeElement);
        });
    }

    document.addEventListener('keydown', function(e) {
        const key = e.key;
        const modifierPressed = isMacPlatform ? e.metaKey : e.ctrlKey;
        if ((key !== 'k' && key !== 'K') || !modifierPressed || e.altKey || e.shiftKey) return;
        if (e.repeat) return;
        if (onboardingState.isOpen) {
            e.preventDefault();
            return;
        }
        if (searchPaletteState.isOpen) {
            e.preventDefault();
            focusPaletteInput();
            return;
        }
        if (logoutDialogState.isOpen || preferencesState.isOpen) return;
        if (isTypingTarget(e.target)) return;
        e.preventDefault();
        openPalette(document.activeElement);
    });

    document.addEventListener('keydown', function(e) {
        if (!searchPaletteState.isOpen || e.isComposing) return;

        if (e.key === 'Escape') {
            e.preventDefault();
            closePalette();
            return;
        }

        // Arrows and Enter drive results only while the input keeps focus
        // (active-descendant pattern); tabs handle their own arrow keys.
        if (e.target !== input) {
            trapFocus(e, panel);
            return;
        }

        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            if (!searchPaletteState.items.length) return;
            const delta = e.key === 'ArrowDown' ? 1 : -1;
            const base = searchPaletteState.activeIndex;
            setActive(base === -1 ? (delta > 0 ? 0 : -1) : base + delta, true);
            return;
        }

        if (e.key === 'Enter') {
            if (searchPaletteState.activeIndex >= 0) {
                e.preventDefault();
                selectIndex(searchPaletteState.activeIndex);
            }
            return;
        }

        trapFocus(e, panel);
    });

    document.addEventListener('quadrum:preferences-open', closePalette);
}

function initDocsPage() {
    const input = document.getElementById('docSearchInput');
    const container = document.getElementById('docIndex');
    const empty = document.getElementById('docSearchEmpty');
    const status = document.getElementById('docSearchStatus');
    if (!input || !container || !empty) return;

    const cards = Array.prototype.slice.call(container.querySelectorAll('.doc-card'));
    const groups = Array.prototype.slice.call(container.querySelectorAll('.doc-index-group'));

    function apply() {
        const query = input.value.trim().toLowerCase();
        let visible = 0;
        cards.forEach(function(card) {
            const haystack = (
                (card.dataset.docKeywords || '') + ' ' + card.textContent
            ).toLowerCase();
            const match = !query || haystack.indexOf(query) !== -1;
            card.hidden = !match;
            if (match) visible += 1;
        });
        groups.forEach(function(group) {
            const any = Array.prototype.some.call(
                group.querySelectorAll('.doc-card'),
                function(card) { return !card.hidden; }
            );
            group.hidden = !any;
        });
        empty.hidden = !(query && visible === 0);
        if (status) {
            status.textContent = query
                ? visible + (visible === 1 ? ' topic matches' : ' topics match')
                : '';
        }
    }

    input.addEventListener('input', apply);
    apply();
}

function initFilters() {
    // Filter search
    const searchInputs = document.querySelectorAll('.search-input');
    searchInputs.forEach(input => {
        input.addEventListener('input', function() {
            const term = this.value.toLowerCase();
            const cards = this.closest('.card')?.querySelectorAll('.product-card') ||
                       document.querySelectorAll('.product-card');

            cards.forEach(card => {
                const name = card.textContent.toLowerCase();
                card.style.display = name.includes(term) ? 'block' : 'none';
            });
        });
    });

    // Filter by category
    window.filterByCategory = function(categoryId) {
        document.querySelectorAll('.category-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        const activeBtn = document.querySelector(`.category-btn[onclick*="${categoryId}"]`);
        if (activeBtn) activeBtn.classList.add('active');

        document.querySelectorAll('.product-card').forEach(card => {
            const category = card.dataset.category;
            if (!categoryId || category == categoryId) {
                card.style.display = '';
            } else {
                card.style.display = 'none';
            }
        });
    };
}

function showNotification(title, message, type = 'info', duration = 5000) {
    const types = {
        success: { bg: 'var(--color-success-bg)', color: 'var(--color-success)', border: 'var(--color-success-border)' },
        warning: { bg: 'var(--color-warning-bg)', color: 'var(--color-warning)', border: 'var(--color-warning-border)' },
        danger: { bg: 'var(--color-danger-bg)', color: 'var(--color-danger)', border: 'var(--color-danger-border)' },
        info: { bg: 'var(--color-info-bg)', color: 'var(--color-info)', border: 'var(--color-info-border)' }
    };

    const config = types[type] || types.info;
    const notification = document.createElement('div');
    notification.className = 'toast toast-' + type;
    notification.style.cssText = `
        position: fixed;
        bottom: var(--space-4);
        right: var(--space-4);
        padding: var(--space-3) var(--space-4);
        border-radius: var(--radius-md);
        font-size: var(--font-size-sm);
        font-weight: var(--font-weight-medium);
        z-index: var(--z-toast);
        box-shadow: var(--shadow-lg);
        background: ${config.bg};
        color: ${config.color};
        border: var(--border-width) solid ${config.border};
        max-width: 320px;
    `;
    notification.innerHTML = `
        <strong>${title || 'Notice'}</strong>
        <span style="margin-left: var(--space-2);">${message || ''}</span>
    `;

    document.body.appendChild(notification);

    // Auto-remove after the given duration (5 seconds by default)
    setTimeout(() => {
        notification.classList.add('removing');
        setTimeout(() => notification.remove(), 300);
    }, duration);

    return notification;
}

function showToast(title, message, type = 'info', duration = 5000) {
    // Template call sites use 'error'; the styling map defines 'danger'.
    const safeType = type === 'error' ? 'danger' : type;
    return showNotification(title, message, safeType, duration);
}

function initNotifications() {
    window.showNotification = showNotification;
    window.showToast = showToast;

    const notificationBtn = document.getElementById('notificationBtn');
    if (notificationBtn && notificationBtn.dataset.bound !== 'true') {
        notificationBtn.dataset.bound = 'true';
        notificationBtn.addEventListener('click', function() {
            togglePanel('notificationPanel');
        });
    }
}

function formatCurrency(value) {
    return 'R$ ' + parseFloat(value || 0).toFixed(2);
}

function copyToClipboard(text, message = 'Copied') {
    const value = String(text == null ? '' : text);

    function copyFallback() {
        const area = document.createElement('textarea');
        area.value = value;
        area.setAttribute('readonly', '');
        area.style.position = 'fixed';
        area.style.opacity = '0';
        document.body.appendChild(area);
        let copied = false;
        try {
            area.select();
            copied = document.execCommand('copy');
        } catch (e) {
            copied = false;
        }
        area.remove();
        return copied;
    }

    function feedback(ok) {
        if (ok) {
            showToast('Copied', message, 'success');
        } else {
            showToast('Copy failed', 'Unable to copy to clipboard', 'error');
        }
        return ok;
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
        return navigator.clipboard.writeText(value)
            .then(() => feedback(true))
            .catch(() => feedback(copyFallback()));
    }
    return Promise.resolve(feedback(copyFallback()));
}

function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// Export required global functions (direct references, available at load time)
window.quadrum = {
    formatCurrency,
    showNotification,
    showToast,
    copyToClipboard,
    toggleSidebar,
    toggleTheme,
    confirmDestructive
};

function setNotificationPanel(open) {
    const panel = document.getElementById('notificationPanel');
    if (!panel) return;
    panel.classList.toggle('open', open);

    const btn = document.getElementById('notificationBtn');
    if (btn) btn.setAttribute('aria-expanded', String(open));
}

window.togglePanel = function(id) {
    const panel = document.getElementById(id);
    if (!panel) return;
    if (id === 'notificationPanel') {
        setNotificationPanel(!panel.classList.contains('open'));
        return;
    }
    panel.classList.toggle('open');
};

document.addEventListener('click', function(e) {
    if (!(e.target instanceof Element)) return;
    const panel = document.getElementById('notificationPanel');
    if (!panel || !panel.classList.contains('open')) return;
    if (e.target.closest('#notificationPanel') || e.target.closest('#notificationBtn')) return;
    setNotificationPanel(false);
});

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') setNotificationPanel(false);
});
