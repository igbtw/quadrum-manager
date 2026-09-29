// ========================================
// MAIN.JS - JavaScript vanilla para o frontend
// ========================================

/* ===== Theme Management ===== */
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

/* ===== Inicialização ===== */
document.addEventListener('DOMContentLoaded', function() {
    // Inicializar tema
    initTheme();
    updateThemeIcon(document.documentElement.getAttribute('data-theme'));
    
    // Inicializar modais
    initModals();
    
    // Inicializar carrinhos
    initCarrinhos();
    
    // Inicializar filtros
    initFiltros();
    
    // Inicializar notificações
    initNotificacoes();
    
    // Inicializar sidebar mobile
    initSidebarMobile();
});

/* ===== Modais ===== */
function initModals() {
    // Abrir modal
    window.openModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('open');
            document.body.style.overflow = 'hidden';
        }
    };

    // Fechar modal
    window.closeModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('open');
            document.body.style.overflow = '';
        }
    };

    // Fechar ao clicar no overlay
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', function(e) {
            if (e.target === this) {
                this.classList.remove('open');
                document.body.style.overflow = '';
            }
        });
    });

    // Fechar com ESC
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

/* ===== Sidebar Mobile ===== */
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

/* ===== Carrinho PDV ===== */
function initCarrinhos() {
    // Inicializar carrinho do PDV
    initPdvCarrinho();
}

function initPdvCarrinho() {
    let carrinho = JSON.parse(localStorage.getItem('cantinaos-carrinho') || '[]');

    // Renderizar carrinho
    renderizarCarrinhoPV(carrinho);

    // Adicionar produto
    window.adicionarAoCarrinhoPV = function(produtoId, nome, preco) {
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
        localStorage.setItem('cantinaos-carrinho', JSON.stringify(carrinho));
        renderizarCarrinhoPV(carrinho);
    };

    // Remover item
    window.removerItemPV = function(idx) {
        carrinho.splice(idx, 1);
        localStorage.setItem('cantinaos-carrinho', JSON.stringify(carrinho));
        renderizarCarrinhoPV(carrinho);
    };

    // Incrementar quantidade
    window.incrementarQtdPV = function(idx) {
        carrinho[idx].qtd += 1;
        localStorage.setItem('cantinaos-carrinho', JSON.stringify(carrinho));
        renderizarCarrinhoPV(carrinho);
    };

    // Decrementar quantidade
    window.decrementarQtdPV = function(idx) {
        if (carrinho[idx].qtd <= 1) {
            removerItemPV(idx);
        } else {
            carrinho[idx].qtd -= 1;
            localStorage.setItem('cantinaos-carrinho', JSON.stringify(carrinho));
            renderizarCarrinhoPV(carrinho);
        }
    };

    function renderizarCarrinhoPV(carrinho) {
        const tabelaBody = document.getElementById('carrinho-tabela-body-pv');
        const carrinhoVazio = document.getElementById('carrinho-vazio-pv');
        const tabela = document.getElementById('carrinho-tabela-pv');
        const resumo = document.getElementById('carrinho-resumo-pv');

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
                        <button onclick="decrementarQtdPV(${idx})" class="btn btn-icon-sm" aria-label="Diminuir quantidade">−</button>
                        <span style="min-width: 24px; text-align: center;">${item.qtd}</span>
                        <button onclick="incrementarQtdPV(${idx})" class="btn btn-icon-sm" aria-label="Aumentar quantidade">+</button>
                    </td>
                    <td style="text-align: right;">R$ ${subtotalItem.toFixed(2)}</td>
                    <td><button class="btn btn-icon-sm btn-danger" onclick="removerItemPV(${idx})" aria-label="Remover item">×</button></td>
                `;
                tabelaBody.appendChild(tr);
            });

            const totalEl = document.getElementById('carrinho-total-pv');
            if (totalEl) totalEl.textContent = 'R$ ' + subtotal.toFixed(2);
        }
    }
}

/* ===== Filtros ===== */
function initFiltros() {
    // Filtro de busca
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
    window.filtrarPorCategoria = function(categoriaId) {
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

/* ===== Notificações ===== */
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
            <strong>${titulo || 'Aviso'}</strong>
            <span style="margin-left: var(--space-2);">${mensagem || ''}</span>
        `;

        document.body.appendChild(notification);

        // Auto remover após 5 segundos
        setTimeout(() => {
            notification.style.transition = 'opacity 0.3s, transform 0.3s';
            notification.style.opacity = '0';
            notification.style.transform = 'translateY(10px)';
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    };
}

/* ===== Utilitários ===== */
function formatarMoeda(valor) {
    return 'R$ ' + parseFloat(valor || 0).toFixed(2);
}

function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// Exportar funções globais necessárias
window.Cantina = {
    formatarMoeda,
    showNotification: window.showNotification,
    toggleSidebar: window.toggleSidebar,
    toggleTheme: toggleTheme
};
