// Main JS — vanilla frontend

function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
    } else {
        document.documentElement.setAttribute('data-theme', systemPrefersDark ? 'dark' : 'light');
    }
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
    const icon = document.getElementById('themeIcon');
    if (icon) {
        if (theme === 'dark') {
            icon.innerHTML = '<path d="M12 3v1m0 16v1m8.66-10.66l-.7.7M5.04 5.04l-.7.7m15.37 7.27a7 7 0 1 1-9.07-9.07 7 7 0 0 0 9.07 9.07z"/>';
        } else {
            icon.innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>';
        }
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Initialize theme
    initTheme();
    updateThemeIcon(document.documentElement.getAttribute('data-theme'));
    
    // Initialize modals
    initModals();
    
    // Initialize filters
    initFiltros();
    
    // Initialize notifications
    initNotificacoes();
    
    // Initialize mobile sidebar
    initSidebarMobile();
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
            document.getElementById('sidebarOverlay')?.classList.remove('visible');
            document.getElementById('sidebar')?.classList.remove('open');
        }
    });
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    if (sidebar) sidebar.classList.toggle('open');
    if (overlay) overlay.classList.toggle('visible');
}

function initSidebarMobile() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');

    if (overlay) {
        overlay.addEventListener('click', function() {
            if (sidebar) sidebar.classList.remove('open');
            this.classList.remove('visible');
        });
    }
}

function initFiltros() {
    // Filter search
    const searchInputs = document.querySelectorAll('.search-input');
    searchInputs.forEach(input => {
        input.addEventListener('input', function() {
            const termo = this.value.toLowerCase();
            const cards = this.closest('.card')?.querySelectorAll('.product-card') ||
                       document.querySelectorAll('.product-card');
            
            cards.forEach(card => {
                const nome = card.textContent.toLowerCase();
                card.style.display = nome.includes(termo) ? 'block' : 'none';
            });
        });
    });

    // Filtro por categoria
    window.filterByCategory = function(categoriaId) {
        document.querySelectorAll('.category-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        const activeBtn = document.querySelector(`.category-btn[onclick*="${categoriaId}"]`);
        if (activeBtn) activeBtn.classList.add('active');
        
        document.querySelectorAll('.product-card').forEach(card => {
            const cat = card.dataset.categoria;
            if (!categoriaId || cat == categoriaId) {
                card.style.display = '';
            } else {
                card.style.display = 'none';
            }
        });
    };
}

function showNotification(titulo, mensagem, tipo = 'info', duracao = 5000) {
    const tipos = {
        success: { bg: 'var(--color-success-bg)', color: 'var(--color-success)', border: 'var(--color-success-border)' },
        warning: { bg: 'var(--color-warning-bg)', color: 'var(--color-warning)', border: 'var(--color-warning-border)' },
        danger: { bg: 'var(--color-danger-bg)', color: 'var(--color-danger)', border: 'var(--color-danger-border)' },
        info: { bg: 'var(--color-info-bg)', color: 'var(--color-info)', border: 'var(--color-info-border)' }
    };

    const config = tipos[tipo] || tipos.info;
    const notification = document.createElement('div');
    notification.className = 'toast toast-' + tipo;
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
        <strong>${titulo || 'Notice'}</strong>
        <span style="margin-left: var(--space-2);">${mensagem || ''}</span>
    `;

    document.body.appendChild(notification);

    // Auto-remove after the given duration (5 seconds by default)
    setTimeout(() => {
        notification.classList.add('removing');
        setTimeout(() => notification.remove(), 300);
    }, duracao);

    return notification;
}

function showToast(titulo, mensagem, tipo = 'info', duracao = 5000) {
    // Template call sites use 'error'; the styling map defines 'danger'.
    const tipoSeguro = tipo === 'error' ? 'danger' : tipo;
    return showNotification(titulo, mensagem, tipoSeguro, duracao);
}

function initNotificacoes() {
    window.showNotification = showNotification;
    window.showToast = showToast;
}

function formatCurrency(valor) {
    return 'R$ ' + parseFloat(valor || 0).toFixed(2);
}

function copyToClipboard(texto, mensagem = 'Copied') {
    const valor = String(texto == null ? '' : texto);

    function copyFallback() {
        const area = document.createElement('textarea');
        area.value = valor;
        area.setAttribute('readonly', '');
        area.style.position = 'fixed';
        area.style.opacity = '0';
        document.body.appendChild(area);
        let copiado = false;
        try {
            area.select();
            copiado = document.execCommand('copy');
        } catch (e) {
            copiado = false;
        }
        area.remove();
        return copiado;
    }

    function feedback(ok) {
        if (ok) {
            showToast('Copied', mensagem, 'success');
        } else {
            showToast('Copy failed', 'Unable to copy to clipboard', 'error');
        }
        return ok;
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
        return navigator.clipboard.writeText(valor)
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
    toggleTheme
};

function toggleSidebarCollapse() {
    document.getElementById('sidebar').classList.toggle('collapsed');
    document.querySelector('.layout')?.classList.toggle('collapsed');
}

window.togglePanel = function(id) {
    var el = document.getElementById(id);
    if (!el) return;
    var isOpen = el.classList.contains('open');
    ['notificationPanel','messagePanel','profileMenu'].forEach(function(pid){
        var p = document.getElementById(pid);
        if (p) p.classList.remove('open');
    });
    if (!isOpen) el.classList.add('open');
};

document.addEventListener('click', function(e){
    if (!e.target.closest('#notificationPanel') && !e.target.closest('.header-right') && document.getElementById('notificationPanel')) document.getElementById('notificationPanel').classList.remove('open');
    if (!e.target.closest('#messagePanel') && !e.target.closest('.header-right') && document.getElementById('messagePanel')) document.getElementById('messagePanel').classList.remove('open');
    if (!e.target.closest('#profileMenu') && !e.target.closest('.user-info') && document.getElementById('profileMenu')) document.getElementById('profileMenu').classList.remove('open');
});
