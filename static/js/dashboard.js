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

/* ── Formatage de montants (sans FCFA) ──────────────────── */
function formaterMontant(montant) {
  if (montant === null || montant === undefined || isNaN(montant)) return '—';
  return Math.round(montant).toLocaleString('fr-FR');
}

/* ── Formatage FCFA (pour contexte spécifique) ───────────── */
function formaterFCFA(montant) {
  const valeur = formaterMontant(montant);
  return valeur === '—' ? '—' : valeur + ' FCFA';
}

/* ── Formatage quantité ──────────────────────────────────── */
function formaterQuantite(qty) {
  if (qty === null || qty === undefined || isNaN(qty)) return '0';
  return Math.round(qty).toString();
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
      // Utiliser formaterMontant() pour les montants, laisser le HTML ajouter FCFA via <span class="currency">FCFA</span>
      set('kpi-revenus',  formaterMontant(data.revenus_jour || 0));
      set('kpi-revenus-mois', formaterMontant(data.revenus_mensuel || 0));
      set('kpi-ventes',   formaterQuantite(data.ventes_jour || 0) + ' produits');
      set('kpi-benefice', formaterMontant(data.benefice_jour || 0));
      set('kpi-pertes',   formaterMontant(data.pertes_jour || 0));
      set('kpi-alertes',  formaterQuantite(data.alertes_stock || 0) + ' produits');
    })
    .catch(() => {});
}

/* ── Stocks critiques (tableau dashboard) ────────────────── */
function chargerStocksCritiques() {
  fetch('/api/dashboard/stocks-critiques')
    .then(r => r.json())
    .then(data => {
      const tbody  = document.querySelector('#table-stocks-critiques tbody');
      const badge  = document.getElementById('badge-critiques');
      const badgeHeader = document.getElementById('badge-critiques-header');
      if (!tbody) return;

      const total = Array.isArray(data.stocks) ? data.stocks.length : 0;
      if (!total) {
        tbody.innerHTML = '<tr><td colspan="5" class="table-empty">✅ Aucun stock critique</td></tr>';
        if (badge) badge.textContent = '0 produit';
        if (badgeHeader) badgeHeader.textContent = '0 produit(s)';
        return;
      }

      if (badge) badge.textContent = total + ' produit(s)';
      if (badgeHeader) badgeHeader.textContent = total + ' produit(s)';

      setupPagination('table-stocks-critiques-container', data.stocks, function(pageData) {
        tbody.innerHTML = pageData.map(p => {
          const qty = p.quantite !== undefined ? p.quantite : '—';
          const seuil = p.seuil_alerte !== undefined ? p.seuil_alerte : '—';
          const isRupture = p.type_alerte === 'rupture' || qty === 0;
          const isPeremption = p.type_alerte === 'peremption';
          
          return `
          <tr>
            <td><strong>${p.nom}</strong></td>
            <td>${badgeSociete(p.societe)}</td>
            <td><strong style="color:${isRupture ? 'var(--red)' : 'inherit'}">${qty}</strong></td>
            <td>${seuil}</td>
            <td>${isPeremption ? `<span style="color:${p.niveau === 'critique' ? 'var(--red)' : 'var(--yellow)'}">${p.message}</span>` : etatStock(qty, seuil)}</td>
          </tr>`;
        }).join('');
      }, 10);
    })
    .catch(() => {});
}

