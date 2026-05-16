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
            tousLesProduits = data.produits;
            remplirSelectProduits(tousLesProduits);
        }
    } catch (error) {
        console.error('Erreur chargement produits:', error);
    }
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
            afficherNotif('✅ Vente enregistrée !', 'success');
            document.getElementById('form-vente').reset();
            document.getElementById('prix-panel').style.display = 'none';
            currentProduct = null;
            
            // Recharger tout
            chargerProduitsSelect();
            chargerVentesJour();
            chargerKPIsCaisse();
            if (typeof chargerGraphVentesHeure === 'function') chargerGraphVentesHeure();
        } else {
            afficherNotif('Erreur : ' + res.message, 'error');
        }
    } catch (error) {
        afficherNotif('Erreur réseau', 'error');
    }
}

function chargerVentesJour() {
    fetch('/api/ventes/aujourdhui')
        .then(r => r.json())
        .then(data => {
            const tbody = document.querySelector('#table-ventes-jour tbody');
            if (data.success && data.ventes.length > 0) {
                tbody.innerHTML = data.ventes.map(v => {
                    const nom = v.nom || v.produit || '—';
                    const prixUnit = v.prix_unitaire || 0;
                    const total = v.quantite * prixUnit;
                    return `
                    <tr>
                        <td>${v.heure || '—'}</td>
                        <td><strong>${nom}</strong></td>
                        <td>${badgeSociete(v.societe)}</td>
                        <td>${v.quantite}</td>
                        <td>${formaterMontant(prixUnit)} FCFA</td>
                        <td><strong>${formaterMontant(total)} FCFA</strong></td>
                    </tr>`;
                }).join('');
                document.getElementById('table-total-encaisse').textContent = formaterMontant(data.total) + ' FCFA';
            } else {
                tbody.innerHTML = '<tr><td colspan="6" class="empty-table">Aucune vente aujourd\'hui</td></tr>';
                document.getElementById('table-total-encaisse').textContent = '0 FCFA';
            }
        });
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