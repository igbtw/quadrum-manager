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
    
    // Initialize carts
    initCarrinhos();
    
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

function initSidebarMobile() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const toggleBtn = document.querySelector('.mobile-menu-btn');

    window.toggleSidebar = function() {
        if (sidebar) sidebar.classList.toggle('open');
        if (overlay) overlay.classList.toggle('visible');
    };

    if (overlay) {
        overlay.addEventListener('click', function() {
            if (sidebar) sidebar.classList.remove('open');
            this.classList.remove('visible');
        });
    }
}

function initCart() {
    // Initialize POS cart
    initPosCart();
}

function initPosCart() {
    let carrinho = JSON.parse(localStorage.getItem('quadrum-carrinho') || '[]');

    // Render cart
    renderCart(carrinho);

    // Add product
    window.addToCart = function(produtoId, nome, preco) {
        const existente = carrinho.find(i => i.id == produtoId);
        if (existente) {
            existente.qtd += 1;
        } else {
            carrinho.push({
                id: produtoId,
                nome: nome,
                preco: preco,
                qtd: 1
            });
        }
        localStorage.setItem('quadrum-carrinho', JSON.stringify(carrinho));
        renderCart(carrinho);
    };

    // Remove item
    window.removeCartItem = function(idx) {
        carrinho.splice(idx, 1);
        localStorage.setItem('quadrum-carrinho', JSON.stringify(carrinho));
        renderCart(carrinho);
    };

    // Increment quantity
    window.increaseQuantity = function(idx) {
        carrinho[idx].qtd += 1;
        localStorage.setItem('quadrum-carrinho', JSON.stringify(carrinho));
        renderCart(carrinho);
    };

    // Decrement quantity
    window.decreaseQuantity = function(idx) {
        if (carrinho[idx].qtd <= 1) {
            removeCartItem(idx);
        } else {
            carrinho[idx].qtd -= 1;
            localStorage.setItem('quadrum-carrinho', JSON.stringify(carrinho));
            renderCart(carrinho);
        }
    };

    function renderCart(carrinho) {
        const tabelaBody = document.getElementById('cart-table-body');
        const carrinhoVazio = document.getElementById('cart-empty');
        const tabela = document.getElementById('cart-table');
        const resumo = document.getElementById('cart-summary');

        if (carrinho.length === 0) {
            tabela.style.display = 'none';
            carrinhoVazio.style.display = 'block';
            resumo.style.display = 'none';
        } else {
            tabela.style.display = 'table';
            carrinhoVazio.style.display = 'none';
            resumo.style.display = 'block';
            
            let subtotal = 0;
            tabelaBody.innerHTML = '';

            carrinho.forEach((item, idx) => {
                const subtotalItem = item.preco * item.qtd;
                subtotal += subtotalItem;

                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${item.nome}</td>
                    <td style="display: flex; align-items: center; gap: var(--space-2);">
                        <button onclick="decreaseQuantity(${idx})" class="btn btn-icon-sm" aria-label="Diminuir quantidade">−</button>
                        <span style="min-width: 24px; text-align: center;">${item.qtd}</span>
                        <button onclick="increaseQuantity(${idx})" class="btn btn-icon-sm" aria-label="Aumentar quantidade">+</button>
                    </td>
                    <td style="text-align: right;">R$ ${subtotalItem.toFixed(2)}</td>
                    <td><button class="btn btn-icon-sm btn-danger" onclick="removeCartItem(${idx})" aria-label="Remover item">×</button></td>
                `;
                tabelaBody.appendChild(tr);
            });

            const totalEl = document.getElementById('cart-total');
            if (totalEl) totalEl.textContent = 'R$ ' + subtotal.toFixed(2);
        }
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

function initNotificacoes() {
    window.showNotification = function(titulo, mensagem, tipo = 'info') {
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

        // Auto-remove after 5 seconds
        setTimeout(() => {
            notification.classList.add('removing');
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    };
}

function formatCurrency(valor) {
    return 'R$ ' + parseFloat(valor || 0).toFixed(2);
}

function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// Export required global functions
window.quadrum = {
    formatCurrency,
    showNotification: window.showNotification,
    toggleSidebar: window.toggleSidebar,
    toggleTheme: toggleTheme
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
