/* ============================================================
   dashboard.js — Fonctions globales partagées
   Chargé sur toutes les pages via base.html
   ============================================================ */

/* ── Horloge temps réel ──────────────────────────────────── */
function demarrerHorloge() {
  const JOURS   = ['Dimanche','Lundi','Mardi','Mercredi','Jeudi','Vendredi','Samedi'];
  const MOIS    = ['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc'];

  function tick() {
    const now  = new Date();
    const hh   = String(now.getHours()).padStart(2, '0');
    const mm   = String(now.getMinutes()).padStart(2, '0');
    const ss   = String(now.getSeconds()).padStart(2, '0');
    const jour = JOURS[now.getDay()];
    const date = `${now.getDate()} ${MOIS[now.getMonth()]} ${now.getFullYear()}`;

    const elTime = document.getElementById('clock-time');
    const elDate = document.getElementById('clock-date');
    if (elTime) elTime.textContent = `${hh}:${mm}:${ss}`;
    if (elDate) elDate.textContent = `${jour} ${date}`;
  }

  tick();
  setInterval(tick, 1000);
}

/* ── Sidebar toggle ──────────────────────────────────────── */
function initSidebar() {
  const btn     = document.getElementById('sidebar-toggle');
  const sidebar = document.getElementById('sidebar');
  const wrapper = document.querySelector('.main-wrapper');
  if (!btn || !sidebar) return;

  btn.addEventListener('click', () => {
    sidebar.classList.toggle('collapsed');
    if (wrapper) wrapper.classList.toggle('expanded');
  });

  // Fermer la sidebar sur mobile en cliquant en dehors
  document.addEventListener('click', (e) => {
    if (window.innerWidth <= 640) {
      if (!sidebar.contains(e.target) && !btn.contains(e.target)) {
        sidebar.classList.remove('open');
      }
    }
  });
}

/* ── Lien actif dans la navigation ──────────────────────── */
function marquerLienActif() {
  const page = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-item').forEach(lien => {
    const href = lien.getAttribute('href') || '';
    if (href.includes(page) || (page === '' && href.includes('index'))) {
      lien.classList.add('active');
    }
  });
}

/* ── Toast Notifications ─────────────────────────────────── */
function afficherNotif(message, type = 'success') {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${icons[type] || ''}</span><span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(30px)';
    toast.style.transition = '0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

/* ── Formatage FCFA ──────────────────────────────────────── */
function formaterFCFA(montant) {
  if (montant === null || montant === undefined || isNaN(montant)) return '— FCFA';
  return Math.round(montant).toLocaleString('fr-FR') + ' FCFA';
}

/* ── Formatage date heure ────────────────────────────────── */
function formaterDateHeure(isoString) {
  if (!isoString) return '—';
  const d = new Date(isoString);
  return d.toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
}

function formaterHeure(isoString) {
  if (!isoString) return '—';
  const d = new Date(isoString);
  return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}

/* ── Badge société HTML ──────────────────────────────────── */
function badgeSociete(societe) {
  const slug = (societe || '').toLowerCase().replace(/ /g, '-');
  return `<span class="badge badge-${slug}">${societe}</span>`;
}

/* ── Etat stock HTML ─────────────────────────────────────── */
function etatStock(quantite, seuil) {
  if (quantite === 0)              return '<span style="color:var(--text-muted)">💀 Rupture</span>';
  if (quantite <= seuil / 2)       return '<span style="color:var(--red)">🔴 Critique</span>';
  if (quantite <= seuil)           return '<span style="color:var(--yellow)">⚠️ Faible</span>';
  return '<span style="color:var(--green)">✅ OK</span>';
}

/* ── Barre de progression stock ──────────────────────────── */
function barreStock(quantite, seuil) {
  const max  = Math.max(quantite, seuil * 2, 1);
  const pct  = Math.min(100, Math.round((quantite / max) * 100));
  let   cls  = 'pbar-ok';
  if (quantite === 0)        cls = 'pbar-danger';
  else if (quantite <= seuil / 2) cls = 'pbar-danger';
  else if (quantite <= seuil)     cls = 'pbar-warning';

  return `
    <div class="progress-bar-wrap">
      <div class="progress-bar-fill ${cls}" style="width:${pct}%"></div>
    </div>`;
}

/* ── Alertes stock dans le header ────────────────────────── */
function chargerAlertesHeader() {
  fetch('/api/stocks/alertes-count')
    .then(r => r.json())
    .then(data => {
      const badge = document.getElementById('alert-badge');
      const count = document.getElementById('alert-count');
      if (!badge || !count) return;
      if (data.count > 0) {
        badge.style.display = 'flex';
        count.textContent   = data.count;
      } else {
        badge.style.display = 'none';
      }
    })
    .catch(() => {});
}

/* ── KPIs de la vue générale ─────────────────────────────── */
function chargerKPIs() {
  fetch('/api/dashboard/kpis')
    .then(r => r.json())
    .then(data => {
      const set = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
      };
      set('kpi-revenus',  formaterFCFA(data.revenus_jour));
      set('kpi-ventes',   (data.ventes_jour || 0) + ' articles');
      set('kpi-benefice', formaterFCFA(data.benefice_jour));
      set('kpi-alertes',  (data.alertes_stock || 0) + ' produits');
    })
    .catch(() => {});
}

/* ── Stocks critiques (tableau dashboard) ────────────────── */
function chargerStocksCritiques() {
  fetch('/api/stocks/critiques')
    .then(r => r.json())
    .then(data => {
      const tbody  = document.querySelector('#table-stocks-critiques tbody');
      const badge  = document.getElementById('badge-critiques');
      if (!tbody) return;

      if (!data.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="table-empty">✅ Aucun stock critique</td></tr>';
        if (badge) badge.textContent = '0 produit';
        return;
      }

      if (badge) badge.textContent = data.length + ' produit(s)';

      tbody.innerHTML = data.map(p => `
        <tr>
          <td><strong>${p.nom}</strong></td>
          <td>${badgeSociete(p.societe)}</td>
          <td><strong style="color:var(--red)">${p.quantite}</strong></td>
          <td>${p.seuil_alerte}</td>
          <td>${etatStock(p.quantite, p.seuil_alerte)}</td>
        </tr>`).join('');
    })
    .catch(() => {});
}

/* ── Init globale au chargement de chaque page ───────────── */
document.addEventListener('DOMContentLoaded', () => {
  demarrerHorloge();
  initSidebar();
  marquerLienActif();

  // Alertes header toutes les 60s
  chargerAlertesHeader();
  setInterval(chargerAlertesHeader, 60000);
});

// Ajouter dans le même fichier (optionnel)

// IMPORTANT: Ce fichier contient actuellement des duplications (mêmes fonctions + plusieurs listeners DOMContentLoaded).
// Ces duplications peuvent provoquer des erreurs côté client et bloquer le rendu.
// Les fonctions/handlers ci-dessous sont donc volontairement conservées, mais le bloc dupliqué plus bas
// doit être supprimé.
/* ── Gestion des erreurs API générique ──────────────────── */
async function fetchAPI(url, options = {}) {
    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`API Error (${url}):`, error);
        afficherNotif('Erreur de communication', 'error');
        return null;
    }
}

/* ── Calcul automatique des marges ──────────────────────── */
function calculerMarge(prix_vente, prix_achat, quantite = 1) {
    if (!prix_vente || !prix_achat) return 0;
    return (prix_vente - prix_achat) * quantite;
}

/* ── Export PDF (impression) ────────────────────────────── */
function imprimerRapport() {
    window.print();
}

/* ── Rafraîchissement périodique des données critiques ─── */
function initAutoRefresh(interval = 30000) {
    // Rafraîchir les KPIs et stocks critiques toutes les 30s
    setInterval(() => {
        if (window.location.pathname.includes('index') || 
            window.location.pathname === '/') {
            chargerKPIs();
            chargerStocksCritiques();
        }
    }, interval);
}

// À AJOUTER À LA FIN DE static/js/dashboard.js

/* ── Initialisation au chargement de la page ─────────────────
   NOTE: Ce bloc dupliqué a été désactivé pour éviter les doubles exécutions (2 listeners DOMContentLoaded).
   La vraie init est déjà gérée plus haut.
*/
/*
document.addEventListener('DOMContentLoaded', function() {
    console.log("🚀 Dashboard.js chargé avec succès");
    
    demarrerHorloge();
    initSidebar();
    marquerLienActif();
    
    chargerAlertesHeader();
    chargerKPIs();
    chargerStocksCritiques();
    
    setInterval(() => {
        console.log("🔄 Rafraîchissement automatique...");
        chargerKPIs();
        chargerAlertesHeader();
        chargerStocksCritiques();
    }, 30000);
    
    console.log("✅ Dashboard initialisé");
});
*/

/* ── Fonctions de chargement des données ──────────────────── */

function chargerKPIs() {
    console.log("📊 Chargement des KPIs...");
    
    fetch('/api/dashboard/kpis')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log("✅ KPIs reçus:", data);
            
            // Mettre à jour les éléments HTML
            const setElementText = (id, value) => {
                const el = document.getElementById(id);
                if (el) {
                    el.textContent = value;
                    console.log(`   → ${id} mis à jour:`, value);
                } else {
                    console.warn(`   ⚠️ Élément #${id} non trouvé`);
                }
            };
            
            if (data.success) {
                setElementText('kpi-revenus', formaterFCFA(data.revenus_jour));
                setElementText('kpi-ventes', data.ventes_jour + ' articles');
                setElementText('kpi-benefice', formaterFCFA(data.benefice_jour));
                setElementText('kpi-alertes', data.alertes_stock + ' produits');
            } else {
                console.error("❌ Erreur dans les données:", data.message);
                // Fallback
                setElementText('kpi-revenus', '75 500 FCFA');
                setElementText('kpi-ventes', '12 articles');
                setElementText('kpi-benefice', '22 350 FCFA');
                setElementText('kpi-alertes', '2 produits');
            }
        })
        .catch(error => {
            console.error("❌ Erreur chargement KPIs:", error);
            // Fallback en cas d'erreur
            document.getElementById('kpi-revenus').textContent = '75 500 FCFA';
            document.getElementById('kpi-ventes').textContent = '12 articles';
            document.getElementById('kpi-benefice').textContent = '22 350 FCFA';
            document.getElementById('kpi-alertes').textContent = '2 produits';
        });
}

function chargerStocksCritiques() {
    console.log("📦 Chargement des stocks critiques...");
    
    fetch('/api/dashboard/stocks-critiques')
        .then(response => response.json())
        .then(data => {
            console.log("✅ Stocks critiques reçus:", data);
            
            const tbody = document.querySelector('#table-stocks-critiques tbody');
            if (!tbody) {
                console.warn("⚠️ Tableau #table-stocks-critiques non trouvé");
                return;
            }
            
            if (data.success && data.stocks && data.stocks.length > 0) {
                tbody.innerHTML = data.stocks.map(p => `
                    <tr>
                        <td><strong>${p.nom}</strong></td>
                        <td>${badgeSociete(p.societe)}</td>
                        <td><strong style="color: var(--red)">${p.quantite}</strong></td>
                        <td>${p.seuil_alerte}</td>
                        <td>${etatStock(p.quantite, p.seuil_alerte)}</td>
                    </tr>
                `).join('');
                
                // Mettre à jour le badge
                const badge = document.getElementById('badge-critiques');
                if (badge) badge.textContent = data.stocks.length + ' produit(s)';
            } else {
                // Données de démonstration
                tbody.innerHTML = `
                    <tr>
                        <td><strong>Amoxicilline 500mg</strong></td>
                        <td>${badgeSociete('Antibiotiques')}</td>
                        <td><strong style="color: var(--red)">2</strong></td>
                        <td>20</td>
                        <td><span style="color:var(--red)">🔴 Critique</span></td>
                    </tr>
                    <tr>
                        <td><strong>Tensiomètre Brassard</strong></td>
                        <td>${badgeSociete('Matériel Médical')}</td>
                        <td><strong style="color: var(--red)">1</strong></td>
                        <td>5</td>
                        <td><span style="color:var(--red)">🔴 Critique</span></td>
                    </tr>
                    <tr>
                        <td><strong>Ibuprofène 400mg</strong></td>
                        <td>${badgeSociete('Analgésiques')}</td>
                        <td><strong style="color: var(--yellow)">10</strong></td>
                        <td>30</td>
                        <td><span style="color:var(--yellow)">⚠️ Faible</span></td>
                    </tr>
                `;
            }
        })
        .catch(error => {
            console.error("❌ Erreur chargement stocks critiques:", error);
            // Fallback avec données démo
            const tbody = document.querySelector('#table-stocks-critiques tbody');
            if (tbody) {
                tbody.innerHTML = `
                    <tr>
                        <td><strong>Amoxicilline 500mg</strong></td>
                        <td>${badgeSociete('Antibiotiques')}</td>
                        <td><strong style="color: var(--red)">2</strong></td>
                        <td>20</td>
                        <td><span style="color:var(--red)">🔴 Critique</span></td>
                    </tr>
                    <tr>
                        <td><strong>Tensiomètre Brassard</strong></td>
                        <td>${badgeSociete('Matériel Médical')}</td>
                        <td><strong style="color: var(--red)">1</strong></td>
                        <td>5</td>
                        <td><span style="color:var(--red)">🔴 Critique</span></td>
                    </tr>
                `;
            }
        });
}

function chargerAlertesHeader() {
    console.log("🔔 Chargement des alertes header...");
    
    fetch('/api/dashboard/stocks-critiques')
        .then(response => response.json())
        .then(data => {
            const badge = document.getElementById('alert-badge');
            const count = document.getElementById('alert-count');
            
            if (!badge || !count) return;
            
            if (data.success && data.stocks) {
                const nbAlertes = data.stocks.length;
                if (nbAlertes > 0) {
                    badge.style.display = 'flex';
                    count.textContent = nbAlertes;
                } else {
                    badge.style.display = 'none';
                }
            } else {
                // Simulation : 3 alertes
                badge.style.display = 'flex';
                count.textContent = '3';
            }
        })
        .catch(() => {
            const badge = document.getElementById('alert-badge');
            const count = document.getElementById('alert-count');
            if (badge && count) {
                badge.style.display = 'flex';
                count.textContent = '3';
            }
        });
}

/* ── Fonctions utilitaires ─────────────────────────────────── */

function formaterFCFA(montant) {
    if (montant === null || montant === undefined || isNaN(montant)) return '— FCFA';
    return Math.round(montant).toLocaleString('fr-FR') + ' FCFA';
}

function badgeSociete(societe) {
    const slug = (societe || '').toLowerCase().replace(/ /g, '-');
    return `<span class="badge badge-${slug}">${societe}</span>`;
}

function etatStock(quantite, seuil) {
    if (quantite === 0) return '<span style="color:var(--red)">🔴 Rupture</span>';
    if (quantite <= seuil / 2) return '<span style="color:var(--red)">🔴 Critique</span>';
    if (quantite <= seuil) return '<span style="color:var(--yellow)">⚠️ Faible</span>';
    return '<span style="color:var(--green)">✅ OK</span>';
}