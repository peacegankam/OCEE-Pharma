/**
 * utils.js - Fonctions partagées pour la pagination et les modals (CRUD)
 */

/* =====================================================================
 * MODALS CRUD
 * ===================================================================== */

/**
 * Affiche un modal de confirmation standard
 * @param {string} titre - Titre du modal
 * @param {string} message - Message de confirmation
 * @param {function} onConfirm - Callback exécuté si l'utilisateur confirme
 */
function showConfirmModal(titre, message, onConfirm) {
    let modal = document.getElementById('crud-confirm-modal');
    if (!modal) {
        console.error("Le modal de confirmation n'existe pas dans base.html");
        // Fallback natif
        if (confirm(titre + "\n\n" + message)) {
            onConfirm();
        }
        return;
    }

    document.getElementById('crud-confirm-title').textContent = titre;
    document.getElementById('crud-confirm-message').textContent = message;

    // Retirer les anciens event listeners (clone trick)
    const btnConfirm = document.getElementById('crud-confirm-btn');
    const newBtnConfirm = btnConfirm.cloneNode(true);
    btnConfirm.parentNode.replaceChild(newBtnConfirm, btnConfirm);

    newBtnConfirm.addEventListener('click', () => {
        closeConfirmModal();
        if (typeof onConfirm === 'function') onConfirm();
    });

    modal.style.display = 'flex';
}

function closeConfirmModal() {
    const modal = document.getElementById('crud-confirm-modal');
    if (modal) modal.style.display = 'none';
}

/**
 * Affiche un modal de succès/validation
 * @param {string} titre - Titre (ex: "Succès")
 * @param {string} message - Message (ex: "Produit supprimé")
 * @param {function} onClose - Optionnel: callback à la fermeture
 */
function showSuccessModal(titre, message, onClose = null) {
    let modal = document.getElementById('crud-success-modal');
    if (!modal) {
        // Fallback natif
        alert(titre + "\n" + message);
        if (typeof onClose === 'function') onClose();
        return;
    }

    document.getElementById('crud-success-title').textContent = titre;
    document.getElementById('crud-success-message').textContent = message;

    const btnOk = document.getElementById('crud-success-btn');
    const newBtnOk = btnOk.cloneNode(true);
    btnOk.parentNode.replaceChild(newBtnOk, btnOk);

    newBtnOk.addEventListener('click', () => {
        closeSuccessModal();
        if (typeof onClose === 'function') onClose();
    });

    modal.style.display = 'flex';
}

function closeSuccessModal() {
    const modal = document.getElementById('crud-success-modal');
    if (modal) modal.style.display = 'none';
}

/* =====================================================================
 * PAGINATION
 * ===================================================================== */

/**
 * Configure la pagination pour un ensemble de données et un rendu de tableau
 * @param {string} containerId - L'ID du conteneur parent (ex: 'table-container') où injecter les boutons
 * @param {Array} data - Le tableau complet des données
 * @param {function} renderCallback - Fonction appelée avec le segment de données (ex: afficherTable(paginatedData))
 * @param {number} itemsPerPage - Éléments par page (défaut 10)
 */
function setupPagination(containerId, data, renderCallback, itemsPerPage = 10) {
    const container = document.getElementById(containerId);
    if (!container) return;

    // Supprimer l'ancienne div de pagination si elle existe
    let oldPagination = container.querySelector('.pagination-controls');
    if (oldPagination) {
        oldPagination.remove();
    }

    if (!data || data.length === 0) {
        renderCallback([]);
        return;
    }

    let currentPage = 1;
    const totalPages = Math.ceil(data.length / itemsPerPage);

    function renderPage(page) {
        currentPage = page;
        const start = (page - 1) * itemsPerPage;
        const end = start + itemsPerPage;
        const paginatedData = data.slice(start, end);
        
        // Rendre les données via la fonction fournie
        renderCallback(paginatedData);
        
        // Mettre à jour les boutons
        updatePaginationUI();
    }

    function updatePaginationUI() {
        if (totalPages <= 1) {
            let existing = container.querySelector('.pagination-controls');
            if (existing) existing.remove();
            return; // Pas besoin de pagination
        }

        let paginationDiv = container.querySelector('.pagination-controls');
        if (!paginationDiv) {
            paginationDiv = document.createElement('div');
            paginationDiv.className = 'pagination-controls';
            paginationDiv.style.display = 'flex';
            paginationDiv.style.justifyContent = 'flex-end';
            paginationDiv.style.alignItems = 'center';
            paginationDiv.style.gap = '5px';
            paginationDiv.style.padding = '15px';
            paginationDiv.style.borderTop = '1px solid var(--border-color)';
            container.appendChild(paginationDiv);
        }

        let html = '';
        html += `<button class="btn-page" data-page="${currentPage - 1}" ${currentPage === 1 ? 'disabled' : ''}><i class="fas fa-chevron-left"></i></button>`;
        
        // Afficher max 5 pages autour de la page courante
        let startPage = Math.max(1, currentPage - 2);
        let endPage = Math.min(totalPages, currentPage + 2);
        
        if (startPage > 1) {
            html += `<button class="btn-page" data-page="1">1</button>`;
            if (startPage > 2) html += `<span style="color:var(--text-muted)">...</span>`;
        }

        for (let i = startPage; i <= endPage; i++) {
            html += `<button class="btn-page ${i === currentPage ? 'active' : ''}" data-page="${i}">${i}</button>`;
        }

        if (endPage < totalPages) {
            if (endPage < totalPages - 1) html += `<span style="color:var(--text-muted)">...</span>`;
            html += `<button class="btn-page" data-page="${totalPages}">${totalPages}</button>`;
        }

        html += `<button class="btn-page" data-page="${currentPage + 1}" ${currentPage === totalPages ? 'disabled' : ''}><i class="fas fa-chevron-right"></i></button>`;

        paginationDiv.innerHTML = html;

        // Écouteurs de clic
        paginationDiv.querySelectorAll('.btn-page').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const page = parseInt(e.currentTarget.getAttribute('data-page'));
                if (page >= 1 && page <= totalPages && page !== currentPage) {
                    renderPage(page);
                }
            });
        });
    }

    // Styles de pagination injectés dynamiquement si non existants
    if (!document.getElementById('pagination-styles')) {
        const style = document.createElement('style');
        style.id = 'pagination-styles';
        style.innerHTML = `
            .btn-page {
                background: rgba(255,255,255,0.05);
                border: 1px solid var(--border-color);
                color: var(--text-light);
                padding: 6px 12px;
                border-radius: 6px;
                cursor: pointer;
                transition: all 0.2s;
            }
            .btn-page:hover:not(:disabled) {
                background: var(--orange);
                border-color: var(--orange);
                color: white;
            }
            .btn-page.active {
                background: var(--orange);
                border-color: var(--orange);
                color: white;
            }
            .btn-page:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
        `;
        document.head.appendChild(style);
    }

    // Init première page
    renderPage(1);
}
