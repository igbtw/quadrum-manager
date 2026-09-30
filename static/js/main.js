// ========================================
// MAIN.JS - JavaScript vanilla para o frontend
// ========================================

/* ===== Global State ===== */
const Cantina = {
    // Theme
    initTheme() {
        const savedTheme = localStorage.getItem('theme');
        const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const theme = savedTheme || (systemPrefersDark ? 'dark' : 'light');
        document.documentElement.setAttribute('data-theme', theme);
        this.updateThemeIcon(theme);
    },

    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        this.updateThemeIcon(newTheme);
        this.showToast('Tema alterado', `Tema ${newTheme === 'dark' ? 'escuro' : 'claro'} ativado`, 'info');
    },

    updateThemeIcon(theme) {
        const icon = document.getElementById('themeIcon');
        if (icon) {
            if (theme === 'dark') {
                icon.innerHTML = '<path d="M12 3v1m0 16v1m8.66-10.66l-.7.7M5.04 5.04l-.7.7m15.37 7.27a7 7 0 1 1-9.07-9.07 7 7 0 0 0 9.07 9.07z"/>';
            } else {
                icon.innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>';
            }
        }
    },

    // Sidebar
    sidebarCollapsed: false,

    initSidebar() {
        const saved = localStorage.getItem('sidebarCollapsed');
        if (saved === 'true') {
            this.sidebarCollapsed = true;
            document.querySelector('.sidebar')?.classList.add('collapsed');
            document.querySelector('.header')?.classList.add('sidebar-collapsed');
            document.querySelector('.main')?.classList.add('sidebar-collapsed');
            this.updateCollapseIcon(true);
        }

        const btn = document.getElementById('sidebarCollapseBtn');
        if (btn) {
            btn.addEventListener('click', () => this.toggleSidebarCollapse());
        }
    },

    toggleSidebarCollapse() {
        this.sidebarCollapsed = !this.sidebarCollapsed;
        document.querySelector('.sidebar')?.classList.toggle('collapsed');
        document.querySelector('.header')?.classList.toggle('sidebar-collapsed');
        document.querySelector('.main')?.classList.toggle('sidebar-collapsed');
        localStorage.setItem('sidebarCollapsed', this.sidebarCollapsed);
        this.updateCollapseIcon(this.sidebarCollapsed);
    },

    updateCollapseIcon(collapsed) {
        const btn = document.getElementById('sidebarCollapseBtn');
        if (btn) {
            const icon = btn.querySelector('svg');
            if (collapsed) {
                icon.innerHTML = '<polyline points="9 18 15 12 9 6"></polyline>';
                btn.setAttribute('aria-label', 'Expandir sidebar');
                btn.setAttribute('data-tooltip', 'Expandir sidebar (Ctrl+B)');
            } else {
                icon.innerHTML = '<polyline points="15 18 9 12 15 6"></polyline>';
                btn.setAttribute('aria-label', 'Colapsar sidebar');
                btn.setAttribute('data-tooltip', 'Colapsar sidebar (Ctrl+B)');
            }
        }
    },

    // Mobile Sidebar
    initSidebarMobile() {
        const sidebar = document.getElementById('sidebar');
        const overlay = document.getElementById('sidebarOverlay');

        window.toggleSidebar = () => {
            sidebar?.classList.toggle('open');
            overlay?.classList.toggle('visible');
        };

        overlay?.addEventListener('click', () => {
            sidebar?.classList.remove('open');
            overlay?.classList.remove('visible');
        });
    },

    // Toast Notifications
    showToast(title, message, type = 'info', duration = 5000) {
        const container = document.getElementById('toastContainer');
        if (!container) return;

        const icons = {
            success: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>',
            warning: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
            danger: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
            info: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>'
        };

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <div class="toast-icon">${icons[type] || icons.info}</div>
            <div class="toast-message">
                <strong>${title}</strong>
                <span>${message}</span>
            </div>
            <button class="toast-close" aria-label="Fechar">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>
        `;

        toast.querySelector('.toast-close').addEventListener('click', () => this.removeToast(toast));
        container.appendChild(toast);

        if (duration > 0) {
            setTimeout(() => this.removeToast(toast), duration);
        }
    },

    removeToast(toast) {
        toast.style.transition = 'opacity 0.3s, transform 0.3s';
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    },

    // Command Palette
    commandPaletteCommands: [
        { id: 'dashboard', title: 'Dashboard', shortcut: 'G D', action: () => window.location.href = '/dashboard/' },
        { id: 'vendas', title: 'Vendas', shortcut: 'G V', action: () => window.location.href = '/vendas/' },
        { id: 'nova-venda', title: 'Nova Venda', shortcut: 'G N', action: () => window.location.href = '/vendas/nova/' },
        { id: 'produtos', title: 'Produtos', shortcut: 'G P', action: () => window.location.href = '/produtos/' },
        { id: 'estoque', title: 'Estoque', shortcut: 'G E', action: () => window.location.href = '/estoque/' },
        { id: 'pessoas', title: 'Pessoas', shortcut: 'G S', action: () => window.location.href = '/pessoas/' },
        { id: 'financeiro', title: 'Financeiro', shortcut: 'G F', action: () => window.location.href = '/financeiro/' },
        { id: 'relatorios', title: 'Relatórios', shortcut: 'G R', action: () => window.location.href = '/relatorios/' },
        { id: 'theme', title: 'Alternar tema', shortcut: 'T', action: () => this.toggleTheme() },
    ],

    initCommandPalette() {
        const overlay = document.getElementById('commandPaletteOverlay');
        const input = document.getElementById('commandPaletteInput');
        const list = document.getElementById('commandPaletteList');
        let selectedIndex = -1;

        const open = () => {
            overlay.classList.add('open');
            input.value = '';
            this.renderCommandList('');
            input.focus();
            selectedIndex = -1;
        };

        const close = () => {
            overlay.classList.remove('open');
            input.value = '';
        };

        const select = (index) => {
            const items = list.querySelectorAll('.command-palette-item');
            items.forEach((item, i) => item.classList.toggle('selected', i === index));
            selectedIndex = index;
        };

        const execute = (index) => {
            const commands = this.getFilteredCommands(input.value);
            if (commands[index]) {
                commands[index].action();
                close();
            }
        };

        const filter = (query) => {
            this.renderCommandList(query);
            selectedIndex = -1;
        };

        input.addEventListener('input', (e) => filter(e.target.value));
        input.addEventListener('keydown', (e) => {
            const items = list.querySelectorAll('.command-palette-item');
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                select(Math.min(selectedIndex + 1, items.length - 1));
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                select(Math.max(selectedIndex - 1, 0));
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (selectedIndex >= 0) execute(selectedIndex);
            } else if (e.key === 'Escape') {
                close();
            }
        });

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) close();
        });

        window.openCommandPalette = open;
        window.closeCommandPalette = close;
    },

    getFilteredCommands(query) {
        const q = query.toLowerCase().trim();
        if (!q) return this.commandPaletteCommands;
        return this.commandPaletteCommands.filter(cmd =>
            cmd.title.toLowerCase().includes(q) ||
            cmd.shortcut.toLowerCase().includes(q)
        );
    },

    renderCommandList(query) {
        const list = document.getElementById('commandPaletteList');
        const commands = this.getFilteredCommands(query);
        list.innerHTML = commands.map((cmd, i) => `
            <div class="command-palette-item" role="option" data-index="${i}" tabindex="-1">
                <div class="command-palette-item-info">
                    <span class="command-palette-item-title">${cmd.title}</span>
                    <span class="command-palette-item-shortcut">${cmd.shortcut}</span>
                </div>
            </div>
        `).join('');

        list.querySelectorAll('.command-palette-item').forEach((item, i) => {
            item.addEventListener('click', () => {
                const commands = this.getFilteredCommands(query);
                if (commands[i]) {
                    commands[i].action();
                    window.closeCommandPalette();
                }
            });
            item.addEventListener('mouseenter', () => {
                const items = list.querySelectorAll('.command-palette-item');
                items.forEach(el => el.classList.remove('selected'));
                item.classList.add('selected');
            });
        });
    },

    // Keyboard Shortcuts Help
    initShortcutsHelp() {
        const overlay = document.getElementById('shortcutsHelpOverlay');
        window.openShortcutsHelp = () => overlay.classList.add('open');
        window.closeShortcutsHelp = () => overlay.classList.remove('open');

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) window.closeShortcutsHelp();
        });
    },

    // Global Search
    initGlobalSearch() {
        const input = document.getElementById('globalSearchInput');
        const results = document.getElementById('globalSearchResults');
        const form = document.getElementById('globalSearchForm');
        let selectedIndex = -1;
        let searchData = [];

        // Mock search data - in real app this would come from API
        const mockData = [
            { type: 'produto', title: 'X-Burger', subtitle: 'Produto • R$ 18,00', url: '/produtos/' },
            { type: 'produto', title: 'Coca-Cola 350ml', subtitle: 'Produto • R$ 6,00', url: '/produtos/' },
            { type: 'produto', title: 'Batata Frita', subtitle: 'Produto • R$ 12,00', url: '/produtos/' },
            { type: 'pessoa', title: 'João Silva', subtitle: 'Aluno • Matrícula: 2024001', url: '/pessoas/' },
            { type: 'pessoa', title: 'Maria Santos', subtitle: 'Professor • Matrícula: 2023005', url: '/pessoas/' },
            { type: 'venda', title: 'VD-20241125-0042', subtitle: 'Venda • R$ 45,00 • João Silva', url: '/vendas/' },
            { type: 'venda', title: 'VD-20241125-0038', subtitle: 'Venda • R$ 28,50 • Maria Santos', url: '/vendas/' },
        ];

        const typeIcons = {
            produto: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path></svg>',
            pessoa: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle></svg>',
            venda: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path><rect x="8" y="2" width="8" height="4" rx="1" ry="1"></rect></svg>',
        };

        const filter = (query) => {
            const q = query.toLowerCase().trim();
            if (!q) {
                results.innerHTML = '';
                results.style.display = 'none';
                return;
            }

            searchData = mockData.filter(item =>
                item.title.toLowerCase().includes(q) ||
                item.subtitle.toLowerCase().includes(q)
            );

            if (searchData.length === 0) {
                results.innerHTML = '<div class="command-palette-empty">Nenhum resultado encontrado</div>';
                results.style.display = 'block';
                return;
            }

            results.innerHTML = searchData.map((item, i) => `
                <div class="command-palette-item" role="option" data-index="${i}" tabindex="-1">
                    <div class="command-palette-item-info">
                        <span class="command-palette-item-title">${typeIcons[item.type] || ''} ${item.title}</span>
                        <span class="command-palette-item-shortcut">${item.subtitle}</span>
                    </div>
                </div>
            `).join('');

            results.style.display = 'block';
            selectedIndex = -1;

            results.querySelectorAll('.command-palette-item').forEach((el, i) => {
                el.addEventListener('click', () => {
                    window.location.href = searchData[i].url;
                });
                el.addEventListener('mouseenter', () => {
                    results.querySelectorAll('.command-palette-item').forEach(x => x.classList.remove('selected'));
                    el.classList.add('selected');
                    selectedIndex = i;
                });
            });
        };

        const select = (index) => {
            const items = results.querySelectorAll('.command-palette-item');
            items.forEach((item, i) => item.classList.toggle('selected', i === index));
            selectedIndex = index;
        };

        input.addEventListener('input', (e) => filter(e.target.value));
        input.addEventListener('focus', () => filter(input.value));
        input.addEventListener('keydown', (e) => {
            const items = results.querySelectorAll('.command-palette-item');
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                select(Math.min(selectedIndex + 1, items.length - 1));
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                select(Math.max(selectedIndex - 1, 0));
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (selectedIndex >= 0 && searchData[selectedIndex]) {
                    window.location.href = searchData[selectedIndex].url;
                }
            } else if (e.key === 'Escape') {
                results.style.display = 'none';
                input.blur();
            }
        });

        document.addEventListener('click', (e) => {
            if (!form.contains(e.target)) {
                results.style.display = 'none';
            }
        });
    },

    // Keyboard Shortcuts System
    initKeyboardShortcuts() {
        const sequenceBuffer = [];
        const SEQUENCE_TIMEOUT = 1000;

        const isTyping = (target) => {
            const tag = target.tagName.toLowerCase();
            return tag === 'input' || tag === 'textarea' || tag === 'select' || target.isContentEditable;
        };

        document.addEventListener('keydown', (e) => {
            // Don't intercept shortcuts when typing
            if (isTyping(e.target)) {
                // Allow Escape to close overlays even when typing
                if (e.key === 'Escape') {
                    this.closeAllOverlays();
                }
                return;
            }

            const isMac = navigator.platform.includes('Mac');
            const ctrlKey = isMac ? e.metaKey : e.ctrlKey;

            // Ctrl/Cmd + K - Command Palette
            if (ctrlKey && e.key === 'k') {
                e.preventDefault();
                window.openCommandPalette?.();
                return;
            }

            // Ctrl/Cmd + B - Toggle Sidebar Collapse
            if (ctrlKey && e.key === 'b') {
                e.preventDefault();
                this.toggleSidebarCollapse();
                return;
            }

            // / - Focus Global Search (only if not in input)
            if (e.key === '/' && !ctrlKey && !e.metaKey) {
                e.preventDefault();
                const input = document.getElementById('globalSearchInput');
                input?.focus();
                return;
            }

            // ? - Show Keyboard Shortcuts Help
            if (e.key === '?' && !ctrlKey && !e.metaKey) {
                e.preventDefault();
                window.openShortcutsHelp?.();
                return;
            }

            // Escape - Close all overlays
            if (e.key === 'Escape') {
                this.closeAllOverlays();
                return;
            }

            // T - Toggle Theme (only if not typing)
            if (e.key === 't' && !ctrlKey && !e.metaKey) {
                this.toggleTheme();
                return;
            }

            // G + Key sequences for navigation
            if (e.key === 'g') {
                sequenceBuffer.push('g');
                setTimeout(() => sequenceBuffer.length = 0, SEQUENCE_TIMEOUT);
                return;
            }

            if (sequenceBuffer.includes('g')) {
                const navMap = {
                    'd': '/dashboard/',
                    'v': '/vendas/',
                    'n': '/vendas/nova/',
                    'p': '/produtos/',
                    'e': '/estoque/',
                    's': '/pessoas/',
                    'f': '/financeiro/',
                    'r': '/relatorios/',
                };
                if (navMap[e.key]) {
                    e.preventDefault();
                    window.location.href = navMap[e.key];
                    sequenceBuffer.length = 0;
                    return;
                }
                sequenceBuffer.length = 0;
            }
        });
    },

    closeAllOverlays() {
        document.querySelectorAll('.modal-overlay.open, .command-palette-overlay.open, .shortcuts-help-overlay.open, .sidebar-overlay.visible').forEach(el => {
            el.classList.remove('open', 'visible');
        });
        document.getElementById('sidebar')?.classList.remove('open');
        document.getElementById('globalSearchResults')?.style.display = 'none';
        document.body.style.overflow = '';
    },

    // Modals
    initModals() {
        window.openModal = (modalId) => {
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.classList.add('open');
                document.body.style.overflow = 'hidden';
                const focusable = modal.querySelector('input, select, button, [tabindex]:not([tabindex="-1"])');
                focusable?.focus();
            }
        };

        window.closeModal = (modalId) => {
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.classList.remove('open');
                document.body.style.overflow = '';
            }
        };

        document.querySelectorAll('.modal-overlay').forEach(overlay => {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) {
                    overlay.classList.remove('open');
                    document.body.style.overflow = '';
                }
            });
        });
    },

    // Copy to Clipboard
    copyToClipboard(text, successMessage = 'Copiado!') {
        navigator.clipboard.writeText(text).then(() => {
            this.showToast('Sucesso', successMessage, 'success');
        }).catch(() => {
            this.showToast('Erro', 'Falha ao copiar', 'danger');
        });
    },

    // Utility
    formatCurrency(value) {
        return 'R$ ' + parseFloat(value || 0).toFixed(2).replace('.', ',');
    },

    debounce(func, wait) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    },

    // Initialize all
    init() {
        this.initTheme();
        this.initSidebar();
        this.initSidebarMobile();
        this.initModals();
        this.initCommandPalette();
        this.initShortcutsHelp();
        this.initGlobalSearch();
        this.initKeyboardShortcuts();
    }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    Cantina.init();

    // Initialize page-specific features
    if (window.initPdv) window.initPdv();
    if (window.initProdutos) window.initProdutos();
    if (window.initEstoque) window.initEstoque();
    if (window.initPessoas) window.initPessoas();
    if (window.initFinanceiro) window.initFinanceiro();
    if (window.initRelatorios) window.initRelatorios();
    if (window.initVendasList) window.initVendasList();
});

// Export for global access
window.Cantina = Cantina;