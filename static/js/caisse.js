/* caisse.js - Version corrigée pour OCEE */

let tousLesProduits = [];
let currentProduct = null;

document.addEventListener('DOMContentLoaded', () => {
    chargerProduitsSelect();
    chargerVentesJour();
    chargerKPIsCaisse();

    const formVente = document.getElementById('form-vente');
    if (formVente) {
        formVente.addEventListener('submit', encaisserVente);
    }
});

/**
 * Charger les produits pour le select
 */
async function chargerProduitsSelect() {
    try {
        const response = await fetch('/api/produits?with_stock=true');
        const data = await response.json();
        if (data.success) {
            tousLesProduits = data.produits.sort((a, b) => (a.nom || '').localeCompare(b.nom || ''));
            remplirSelectProduits(tousLesProduits);
            remplirSocietesVente();
        }
    } catch (error) {
        console.error('Erreur chargement produits:', error);
    }
}

function remplirSocietesVente() {
    const select = document.getElementById('vente-societe-filtre');
    if (!select) return;

    const societes = [...new Set(tousLesProduits.map(p => p.societe).filter(Boolean))].sort((a, b) => a.localeCompare(b));
    select.innerHTML = '<option value="">Toutes</option>' + societes.map(s => `<option value="${s}">${s}</option>`).join('');
}

function remplirSelectProduits(produits) {
    const select = document.getElementById('vente-produit');
    if (!select) return;

    const currentVal = select.value;
    select.innerHTML = '<option value="">— Sélectionner un produit —</option>' +
        produits.map(p => {
            const stockNote = p.stock_actuel <= 0 ? ' (RUPTURE)' : ` (Stock: ${p.stock_actuel})`;
            return `<option value="${p.id}" ${p.stock_actuel <= 0 ? 'disabled' : ''}>${p.nom}${stockNote}</option>`;
        }).join('');

    select.value = currentVal;
}

function filtrerProduitsVente() {
    const societe = document.getElementById('vente-societe-filtre').value;
    if (!societe) {
        remplirSelectProduits(tousLesProduits);
    } else {
        const filtrés = tousLesProduits.filter(p => p.societe === societe);
        remplirSelectProduits(filtrés);
    }
}

function mettreAJourPrixVente() {
    const id = document.getElementById('vente-produit').value;
    const panel = document.getElementById('prix-panel');

    if (!id) {
        panel.style.display = 'none';
        currentProduct = null;
        return;
    }

    currentProduct = tousLesProduits.find(p => p.id == id);
    if (currentProduct) {
        panel.style.display = 'block';
        // Afficher le prix unitaire avec FCFA
        document.getElementById('prix-unitaire').textContent = formaterMontant(currentProduct.prix_vente) + ' FCFA';
        // Afficher juste la quantité, pas de FCFA
        document.getElementById('stock-dispo').textContent = currentProduct.stock_actuel;

        const badge = document.getElementById('stock-dispo');
        if (currentProduct.stock_actuel <= 5) {
            badge.style.color = 'var(--red)';
            badge.style.fontWeight = 'bold';
        } else {
            badge.style.color = 'var(--green)';
            badge.style.fontWeight = 'normal';
        }

        mettreAJourTotalVente();
    }
}

function mettreAJourTotalVente() {
    if (!currentProduct) return;
    const qte = parseInt(document.getElementById('vente-quantite').value) || 1;
    const total = qte * currentProduct.prix_vente;
    // Afficher le montant avec FCFA
    document.getElementById('total-vente').textContent = formaterMontant(total) + ' FCFA';
}

function ajusterQte(delta) {
    const input = document.getElementById('vente-quantite');
    const newVal = Math.max(1, parseInt(input.value || 1) + delta);

    if (currentProduct && newVal > currentProduct.stock_actuel) {
        afficherNotif('Stock insuffisant !', 'warning');
        return;
    }

    input.value = newVal;
    mettreAJourTotalVente();
}

async function encaisserVente(e) {
    e.preventDefault();
    if (!currentProduct) return;

    const qte = parseInt(document.getElementById('vente-quantite').value);

    if (qte > currentProduct.stock_actuel) {
        afficherNotif('Stock insuffisant pour cette vente', 'error');
        return;
    }

    const data = {
        ventes: [{
            produit_id: currentProduct.id,
            quantite: qte,
            prix_unitaire: currentProduct.prix_vente
        }]
    };

    try {
        const response = await fetch('/api/ventes/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const res = await response.json();

        if (res.success) {
            document.getElementById('form-vente').reset();
            document.getElementById('prix-panel').style.display = 'none';
            currentProduct = null;

            // Recharger tout
            chargerProduitsSelect();
            chargerVentesJour();
            chargerKPIsCaisse();
            if (typeof chargerGraphVentesHeure === 'function') chargerGraphVentesHeure();

            afficherNotif('&#10003; Vente encaissée avec succès', 'success');
        } else {
            afficherNotif('Erreur : ' + res.message, 'error');
        }
    } catch (error) {
        afficherNotif('Erreur réseau', 'error');
    }
}

// ───── Tableau des ventes avec filtres + pagination ─────

let _toutesLesVentes = [];   // Cache complet
let _debounceTimer = null;

function chargerVentesJour() {
    appliquerFiltres();
}

function appliquerFiltres() {
    clearTimeout(_debounceTimer);
    _debounceTimer = setTimeout(_fetchVentes, 300);
}

function reinitFiltres() {
    document.getElementById('filtre-periode').value = 'jour';
    document.getElementById('filtre-produit').value = '';
    document.getElementById('filtre-qte-op').value = '';
    document.getElementById('filtre-qte-val').value = '';
    _fetchVentes();
}

function _fetchVentes() {
    const periode = document.getElementById('filtre-periode')?.value || 'jour';
    const produit = document.getElementById('filtre-produit')?.value || '';
    const qteOp = document.getElementById('filtre-qte-op')?.value || '';
    const qteVal = document.getElementById('filtre-qte-val')?.value || '';

    let url = `/api/ventes/filtres?periode=${periode}`;
    if (produit) url += `&produit=${encodeURIComponent(produit)}`;
    if (qteOp) url += `&qte_op=${encodeURIComponent(qteOp)}`;
    if (qteVal !== '') url += `&qte_val=${encodeURIComponent(qteVal)}`;

    // Indicateur chargement
    const tbody = document.querySelector('#table-ventes-jour tbody');
    if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="empty-table">Chargement...</td></tr>';

    fetch(url)
        .then(r => r.json())
        .then(data => {
            _toutesLesVentes = data.success ? data.ventes : [];
            const total = data.success ? data.total : 0;

            // Badge et total
            const badge = document.getElementById('badge-nb-ventes');
            if (badge) badge.textContent = `${_toutesLesVentes.length} vente(s)`;
            const totEl = document.getElementById('table-total-encaisse');
            if (totEl) totEl.textContent = formaterMontant(total) + ' FCFA';

            // Pagination via utils.js
            setupPagination('ventes-table-container', _toutesLesVentes, _renderVentes, 15);
        })
        .catch(() => {
            if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="empty-table">Erreur de chargement</td></tr>';
        });
}

function _renderVentes(ventes) {
    const tbody = document.querySelector('#table-ventes-jour tbody');
    if (!tbody) return;
    if (!ventes || ventes.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty-table">Aucune vente trouvée</td></tr>';
        return;
    }
    tbody.innerHTML = ventes.map(v => {
        const nom = v.nom || v.produit || '—';
        const prix = v.prix_unitaire || 0;
        const dateVente = v.date_vente || '';
        return `
        <tr>
            <td>${v.date || '—'}</td>
            <td>${v.heure || '—'}</td>
            <td><strong>${nom}</strong></td>
            <td>${badgeSociete(v.societe)}</td>
            <td>${v.quantite}</td>
            <td>${formaterMontant(prix)} FCFA</td>
            <td><strong>${formaterMontant(v.total)} FCFA</strong></td>
            <td>
                <button onclick="telechargerFacture(${v.id})"
                    title="Télécharger le ticket"
                    style="background:rgba(193,68,14,0.15); border:1px solid rgba(193,68,14,0.4); border-radius:6px; padding:4px 8px; color:var(--orange); cursor:pointer; font-size:12px;">
                    &#128444; Facture
                </button>
            </td>
        </tr>`;
    }).join('');
}

function telechargerFacture(venteId) {
    if (!venteId) { afficherNotif('ID de vente introuvable', 'error'); return; }
    window.open('/api/rapports/facture?vente_id=' + venteId, '_blank');
}


function chargerKPIsCaisse() {
    fetch('/api/ventes/aujourdhui')
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                document.getElementById('caisse-total').textContent = formaterMontant(data.total || 0) + ' FCFA';
                document.getElementById('caisse-nb').textContent = (data.nb_ventes || 0);
                document.getElementById('caisse-benefice').textContent = formaterMontant(data.benefice || 0) + ' FCFA';
            }
        });
}

async function annulerDerniereVente() {
    if (!confirm('Voulez-vous vraiment annuler la dernière vente ?')) return;

    try {
        const response = await fetch('/api/ventes/annuler-derniere', { method: 'POST' });
        const res = await response.json();
        if (res.success) {
            afficherNotif('Vente annulée avec succès', 'success');
            chargerVentesJour();
            chargerKPIsCaisse();
            chargerProduitsSelect();
        } else {
            afficherNotif(res.message, 'error');
        }
    } catch (error) {
        afficherNotif('Erreur réseau', 'error');
    }
}