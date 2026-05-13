/* ============================================================
   stocks.js — Gestion complète des stocks
   Alertes, ajustements, historique, commandes
   Dépend de dashboard.js (formaterFCFA, afficherNotif, etc.)
   ============================================================ */

document.addEventListener('DOMContentLoaded', function() {
    // ========== ÉLÉMENTS DOM ==========
    // Filtres
    const filterSociete = document.getElementById('filter-societe');
    const filterSearch = document.getElementById('filter-search');
    const filterStock = document.getElementById('filter-stock');
    const btnAppliquerFiltres = document.getElementById('appliquer-filtres');
    
    // Tableau des stocks
    const stocksTableBody = document.querySelector('#stocks-table tbody');
    const stockCountSpan = document.getElementById('stock-count');
    const stockValeurSpan = document.getElementById('stock-valeur');
    
    // Graphiques
    const stockChart = document.getElementById('stock-chart');
    const stockHistoChart = document.getElementById('stock-histo-chart');
    
    // Modal d'ajustement
    const ajustementModal = document.getElementById('ajustement-modal');
    const ajustementForm = document.getElementById('ajustement-form');
    const btnOuvrirAjustement = document.getElementById('btn-ajuster-stock');
    const btnFermerModal = document.querySelectorAll('[data-dismiss="modal"]');
    
    // Historique
    const histoFilter = document.getElementById('histo-filter');
    const histoPeriod = document.getElementById('histo-period');
    const histoTableBody = document.querySelector('#histo-table tbody');
    
    // Alertes et notifications
    const alertesContainer = document.getElementById('alertes-container');
    const btnRefreshAlertes = document.getElementById('refresh-alertes');
    
    // ========== ÉTAT GLOBAL ==========
    let stocksData = [];
    let alertesData = [];
    let historiqueData = [];
    let produitEnCours = null;
    
    // ========== INITIALISATION ==========
    chargerVueGlobale();
    chargerStocks();
    chargerHistorique();
    chargerAlertes();
    
    // ========== ÉCOUTEURS D'ÉVÉNEMENTS ==========
    
    if (btnAppliquerFiltres) {
        btnAppliquerFiltres.addEventListener('click', appliquerFiltres);
    }
    
    if (btnOuvrirAjustement) {
        btnOuvrirAjustement.addEventListener('click', ouvrirModalAjustement);
    }
    
    if (ajustementForm) {
        ajustementForm.addEventListener('submit', soumettreAjustement);
    }
    
    if (btnRefreshAlertes) {
        btnRefreshAlertes.addEventListener('click', chargerAlertes);
    }
    
    if (filterSociete || filterSearch || filterStock) {
        document.querySelectorAll('#filter-societe, #filter-search, #filter-stock').forEach(el => {
            if (el) el.addEventListener('change', appliquerFiltres);
        });
        if (filterSearch) filterSearch.addEventListener('keyup', debounce(appliquerFiltres, 500));
    }
    
    if (histoFilter) histoFilter.addEventListener('change', chargerHistorique);
    if (histoPeriod) histoPeriod.addEventListener('change', chargerHistorique);
    
    // Fermeture des modals
    btnFermerModal.forEach(btn => {
        btn.addEventListener('click', () => {
            if (ajustementModal) ajustementModal.style.display = 'none';
        });
    });
    
    // ========== FONCTIONS PRINCIPALES ==========
    
    /**
     * Charger la vue globale du stock (KPIs)
     */
    function chargerVueGlobale() {
        fetch('/api/stocks/global')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    if (stockCountSpan) stockCountSpan.textContent = data.total_produits;
                    if (stockValeurSpan) stockValeurSpan.textContent = formaterFCFA(data.valeur_totale);
                }
            })
            .catch(() => afficherNotif('Erreur chargement vue globale', 'error'));
    }
    
    /**
     * Charger la liste complète des stocks
     */
    function chargerStocks() {
        fetch('/api/stocks')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    stocksData = data.stocks;
                    afficherStocks(stocksData);
                    chargerGraphStocksBas(); // Du charts.js
                } else {
                    afficherNotif('Erreur chargement stocks', 'error');
                }
            })
            .catch(() => afficherNotif('Erreur réseau stocks', 'error'));
    }
    
    /**
     * Afficher les stocks dans le tableau
     */
    function afficherStocks(stocks) {
        if (!stocksTableBody) return;
        
        if (!stocks.length) {
            stocksTableBody.innerHTML = '<tr><td colspan="8" class="table-empty">Aucun produit en stock</td></tr>';
            return;
        }
        
        stocksTableBody.innerHTML = stocks.map(p => {
            const stockClass = p.quantite === 0 ? 'stock-rupture' :
                              p.quantite <= p.seuil_alerte / 2 ? 'stock-critique' :
                              p.quantite <= p.seuil_alerte ? 'stock-faible' : 'stock-ok';
            
            return `
                <tr>
                    <td><strong>${p.nom}</strong></td>
                    <td>${badgeSociete(p.societe)}</td>
                    <td class="stock-quantite ${stockClass}">${p.quantite}</td>
                    <td>${p.seuil_alerte}</td>
                    <td>${p.prix_achat} FCFA</td>
                    <td>${p.prix_vente} FCFA</td>
                    <td>${formaterFCFA(p.valeur)}</td>
                    <td>
                        <button class="btn-ajuster" data-id="${p.id}" data-nom="${p.nom}" data-stock="${p.quantite}" data-seuil="${p.seuil_alerte}">
                            ⚡ Ajuster
                        </button>
                        <button class="btn-commander" data-id="${p.id}" data-nom="${p.nom}">
                            📦 Commander
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
        
        // Ajouter les écouteurs sur les boutons
        document.querySelectorAll('.btn-ajuster').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.target.dataset.id;
                const nom = e.target.dataset.nom;
                const stock = parseInt(e.target.dataset.stock);
                const seuil = parseInt(e.target.dataset.seuil);
                ouvrirModalAjustement(id, nom, stock, seuil);
            });
        });
        
        document.querySelectorAll('.btn-commander').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.target.dataset.id;
                const nom = e.target.dataset.nom;
                commanderProduit(id, nom);
            });
        });
    }
    
    /**
     * Appliquer les filtres au tableau
     */
    function appliquerFiltres() {
        let filtered = [...stocksData];
        
        // Filtre par société
        if (filterSociete && filterSociete.value !== 'tous') {
            filtered = filtered.filter(p => p.societe === filterSociete.value);
        }
        
        // Filtre par recherche
        if (filterSearch && filterSearch.value) {
            const search = filterSearch.value.toLowerCase();
            filtered = filtered.filter(p => p.nom.toLowerCase().includes(search));
        }
        
        // Filtre par état de stock
        if (filterStock && filterStock.value !== 'tous') {
            switch(filterStock.value) {
                case 'rupture':
                    filtered = filtered.filter(p => p.quantite === 0);
                    break;
                case 'critique':
                    filtered = filtered.filter(p => p.quantite > 0 && p.quantite <= p.seuil_alerte / 2);
                    break;
                case 'faible':
                    filtered = filtered.filter(p => p.quantite <= p.seuil_alerte && p.quantite > p.seuil_alerte / 2);
                    break;
                case 'ok':
                    filtered = filtered.filter(p => p.quantite > p.seuil_alerte);
                    break;
            }
        }
        
        afficherStocks(filtered);
    }
    
    /**
     * Ouvrir le modal d'ajustement de stock
     */
    function ouvrirModalAjustement(id = null, nom = '', stock = 0, seuil = 0) {
        if (!ajustementModal) return;
        
        produitEnCours = { id, nom, stock, seuil };
        
        const modalTitle = document.getElementById('ajustement-modal-title');
        const productName = document.getElementById('ajustement-product-name');
        const productStock = document.getElementById('ajustement-product-stock');
        const quantiteInput = document.getElementById('ajustement-quantite');
        const typeSelect = document.getElementById('ajustement-type');
        const raisonInput = document.getElementById('ajustement-raison');
        const nouveauStockSpan = document.getElementById('nouveau-stock');
        
        if (id) {
            // Mode édition pour un produit spécifique
            modalTitle.textContent = `Ajuster le stock : ${nom}`;
            productName.textContent = nom;
            productStock.textContent = `${stock} unités (seuil: ${seuil})`;
            
            // Pré-remplir
            quantiteInput.value = '';
            typeSelect.value = 'ajout';
            raisonInput.value = '';
            
            // Calculer le nouveau stock en temps réel
            quantiteInput.addEventListener('input', () => {
                const qte = parseInt(quantiteInput.value) || 0;
                const type = typeSelect.value;
                const nouveau = type === 'ajout' ? stock + qte : stock - qte;
                nouveauStockSpan.textContent = `${Math.max(0, nouveau)} unités`;
            });
            
            typeSelect.addEventListener('change', () => {
                const qte = parseInt(quantiteInput.value) || 0;
                const type = typeSelect.value;
                const nouveau = type === 'ajout' ? stock + qte : stock - qte;
                nouveauStockSpan.textContent = `${Math.max(0, nouveau)} unités`;
            });
            
            ajustementModal.style.display = 'flex';
        } else {
            // Mode création d'ajustement sans produit spécifique
            // Rediriger vers la page produit pour créer un produit d'abord
            window.location.href = '/produits?action=ajouter';
        }
    }
    
    /**
     * Soumettre un ajustement de stock
     */
    function soumettreAjustement(e) {
        e.preventDefault();
        
        if (!produitEnCours || !produitEnCours.id) {
            afficherNotif('Produit non sélectionné', 'error');
            return;
        }
        
        const quantite = parseInt(document.getElementById('ajustement-quantite').value);
        const type = document.getElementById('ajustement-type').value;
        const raison = document.getElementById('ajustement-raison').value;
        
        if (!quantite || quantite <= 0) {
            afficherNotif('Quantité invalide', 'error');
            return;
        }
        
        const data = {
            produit_id: produitEnCours.id,
            quantite: quantite,
            type: type, // 'ajout' ou 'retrait'
            raison: raison || (type === 'ajout' ? 'Ajustement manuel (ajout)' : 'Ajustement manuel (retrait)')
        };
        
        fetch('/api/stocks/ajuster', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                afficherNotif('Stock ajusté avec succès', 'success');
                if (ajustementModal) ajustementModal.style.display = 'none';
                chargerStocks(); // Recharger la liste
                chargerHistorique(); // Recharger l'historique
                chargerAlertes(); // Mettre à jour les alertes
            } else {
                afficherNotif(data.message || 'Erreur lors de l\'ajustement', 'error');
            }
        })
        .catch(() => afficherNotif('Erreur réseau', 'error'));
    }
    
    /**
     * Commander un produit (redirection vers page appro)
     */
    function commanderProduit(id, nom) {
        if (confirm(`Commander ${nom} ?`)) {
            window.location.href = `/appro?product=${id}`;
        }
    }
    
    /**
     * Charger l'historique des mouvements de stock
     */
    function chargerHistorique() {
        const filtre = histoFilter ? histoFilter.value : 'tous';
        const periode = histoPeriod ? histoPeriod.value : 7;
        
        fetch(`/api/stocks/historique?filtre=${filtre}&periode=${periode}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    historiqueData = data.mouvements;
                    afficherHistorique(historiqueData);
                }
            })
            .catch(() => {});
    }
    
    /**
     * Afficher l'historique dans le tableau
     */
    function afficherHistorique(mouvements) {
        if (!histoTableBody) return;
        
        if (!mouvements.length) {
            histoTableBody.innerHTML = '<tr><td colspan="5" class="table-empty">Aucun mouvement récent</td></tr>';
            return;
        }
        
        histoTableBody.innerHTML = mouvements.map(m => {
            const typeClass = m.type === 'ajout' ? 'text-success' : 'text-danger';
            const typeIcon = m.type === 'ajout' ? '➕' : '➖';
            
            return `
                <tr>
                    <td>${formaterDateHeure(m.date)}</td>
                    <td><strong>${m.produit}</strong></td>
                    <td class="${typeClass}">${typeIcon} ${m.type === 'ajout' ? '+' : '-'}${m.quantite}</td>
                    <td>${m.raison || '—'}</td>
                    <td>${m.responsable || 'Pharmacien'}</td>
                </tr>
            `;
        }).join('');
    }
    
    /**
     * Charger les alertes stock
     */
    function chargerAlertes() {
        fetch('/api/stocks/alertes')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alertesData = data.alertes;
                    afficherAlertes(alertesData);
                }
            })
            .catch(() => {});
    }
    
    /**
     * Afficher les alertes dans le conteneur
     */
    function afficherAlertes(alertes) {
        if (!alertesContainer) return;
        
        if (!alertes.length) {
            alertesContainer.innerHTML = '<div class="empty-state">✅ Aucune alerte stock</div>';
            return;
        }
        
        alertesContainer.innerHTML = alertes.map(a => {
            const levelClass = a.niveau === 'critique' ? 'alerte-critique' :
                              a.niveau === 'faible' ? 'alerte-faible' : 'alerte-info';
            
            return `
                <div class="alerte-item ${levelClass}">
                    <div class="alerte-icon">${a.niveau === 'critique' ? '🔴' : a.niveau === 'faible' ? '⚠️' : 'ℹ️'}</div>
                    <div class="alerte-content">
                        <div class="alerte-title"><strong>${a.produit}</strong> (${a.societe})</div>
                        <div class="alerte-message">${a.message}</div>
                        <div class="alerte-action">
                            <button onclick="window.location.href='/appro?product=${a.produit_id}'" class="btn-small">
                                Commander
                            </button>
                            <button onclick="document.querySelector('[data-id=\\'${a.produit_id}\\']').click()" class="btn-small btn-ghost">
                                Ajuster
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }
    
    /**
     * Debounce pour éviter trop d'appels
     */
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    /**
     * Rafraîchir toutes les données
     */
    window.rafraichirStocks = function() {
        chargerVueGlobale();
        chargerStocks();
        chargerHistorique();
        chargerAlertes();
        afficherNotif('Données actualisées', 'success');
    };
});