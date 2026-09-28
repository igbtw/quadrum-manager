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
}

/* ===== Inicialização ===== */
document.addEventListener('DOMContentLoaded', function() {
    // Inicializar tema
    initTheme();
    
    // Inicializar tooltips e modais
    initModals();
    
    // Inicializar carrinhos
    initCarrinhos();
    
    // Inicializar filtros
    initFiltros();
    
    // Inicializar notificações
    initNotificacoes();
});

/* ===== Modais ===== */
function initModals() {
    // Abrir modal
    window.openModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('open');
            document.getElementById('sidebarOverlay').classList.add('visible');
        }
    };

    // Fechar modal
    window.closeModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('open');
            document.getElementById('sidebarOverlay').classList.remove('visible');
        }
    };

    // Alternar sidebar mobile
    window.toggleSidebar = function() {
        const sidebar = document.getElementById('sidebar');
        const overlay = document.getElementById('sidebarOverlay');
        if (sidebar) sidebar.classList.toggle('open');
        if (overlay) overlay.classList.toggle('visible');
    };

    // Fechar ao clicar no overlay
    const overlay = document.getElementById('sidebarOverlay');
    if (overlay) {
        overlay.addEventListener('click', function() {
            const sidebar = document.getElementById('sidebar');
            if (sidebar) sidebar.classList.remove('open');
            this.classList.remove('visible');
        });
    }

    // Fechar com ESC
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const openModals = document.querySelectorAll('.modal-overlay.open');
            openModals.forEach(modal => closeModal(modal.id));
            document.getElementById('sidebarOverlay')?.classList.remove('visible');
        }
    });
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
        document.querySelectorAll('.product-card').forEach((card, i) => {
            // Simples filtro visual
            if (categoriaId === 0) {
                card.style.boxShadow = '';
            } else {
                card.style.boxShadow = i % 2 === 0 ? '0 0 0 2px var(--color-primary)' : '';
            }
        });
    };
}

/* ===== Notificações ===== */
function initNotificacoes() {
    window.showNotification = function(titulo, mensagem, tipo = 'info') {
        const tipos = {
            success: { bg: 'var(--color-success-bg)', color: 'var(--color-success)' },
            warning: { bg: 'var(--color-warning-bg)', color: 'var(--color-warning)' },
            danger: { bg: 'var(--color-danger-bg)', color: 'var(--color-danger)' },
            info: { bg: 'var(--color-info-bg)', color: 'var(--color-info)' }
        };

        const config = tipos[tipo] || tipos.info;
        const notification = document.createElement('div');
        notification.style.position = 'fixed';
        notification.style.bottom = 'var(--space-6)';
        notification.style.left = 'var(--space-6)';
        notification.style.right = 'auto';
        notification.style.background = config.bg;
        notification.style.color = config.color;
        notification.style.padding = 'var(--space-4) var(--space-5)';
        notification.style.borderRadius = 'var(--radius-md)';
        notification.style.boxShadow = 'var(--shadow-md)';
        notification.style.zIndex = 'var(--z-toast)';
        notification.style.maxWidth = '300px';
        notification.innerHTML = `
            <strong>${titulo || 'Aviso'}</strong>
            <span style="margin-left: var(--space-4);">${mensagem || ''}</span>
        `;

        document.body.appendChild(notification);

        // Auto remover após 5 segundos
        setTimeout(() => {
            notification.style.transition = 'opacity 0.3s';
            notification.style.opacity = '0';
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
