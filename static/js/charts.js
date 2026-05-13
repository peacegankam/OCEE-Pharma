/* ============================================================
   charts.js — Tous les graphiques Chart.js
   Couleurs calées sur le thème sombre du dashboard
   ============================================================ */

/* ── Config globale Chart.js ─────────────────────────────── */
Chart.defaults.color          = '#A8A09A';
Chart.defaults.borderColor    = 'rgba(244,162,97,0.1)';
Chart.defaults.font.family    = "'DM Sans', system-ui, sans-serif";
Chart.defaults.font.size      = 12;
Chart.defaults.plugins.legend.labels.boxWidth = 12;
Chart.defaults.plugins.legend.labels.padding  = 16;

/* ── Palette de couleurs ─────────────────────────────────── */
const COULEURS = {
  orange:  '#C1440E',
  warm:    '#F4A261',
  green:   '#2EC4B6',
  blue:    '#4A90D9',
  red:     '#E63946',
  yellow:  '#FFB627',
  purple:  '#9B5DE5',
  muted:   '#6A6460',
};

const COULEURS_SOCIETES = {
  'Antibiotiques':    '#2A9D8F',
  'Analgésiques':    '#E76F51',
  'Vitamines':       '#F4A261',
  'Dermatologie':    '#E9C46A',
  'Matériel Médical': '#264653',
};

/* Registre des instances Chart pour destruction propre */
const _charts = {};

function detruireChart(id) {
  if (_charts[id]) { _charts[id].destroy(); delete _charts[id]; }
}

/* ── Options de base réutilisables ───────────────────────── */
function optsBase(extra = {}) {
  return {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#161628',
        borderColor:      'rgba(244,162,97,0.25)',
        borderWidth:      1,
        titleColor:       '#F4A261',
        bodyColor:        '#F0EAD6',
        padding:          10,
        cornerRadius:     8,
        callbacks: {
          label: ctx => ' ' + formaterFCFA(ctx.parsed.y ?? ctx.parsed)
        }
      }
    },
    scales: {
      x: {
        grid:  { color: 'rgba(255,255,255,0.04)', drawBorder: false },
        ticks: { color: '#A8A09A', maxRotation: 30 }
      },
      y: {
        grid:  { color: 'rgba(255,255,255,0.06)', drawBorder: false },
        ticks: {
          color: '#A8A09A',
          callback: v => Math.round(v).toLocaleString('fr-FR')
        },
        beginAtZero: true
      }
    },
    ...extra
  };
}

/* ── 1. Graphique revenus de la semaine (ligne) ──────────── */
function chargerRevenusSemaine() {
  fetch('/api/dashboard/revenus-semaine')
    .then(r => r.json())
    .then(data => {
      const ctx = document.getElementById('chart-revenus-semaine');
      if (!ctx) return;
      detruireChart('revenus-semaine');

      _charts['revenus-semaine'] = new Chart(ctx, {
        type: 'line',
        data: {
          labels:   data.map(d => d.date),
          datasets: [{
            label:           'Revenus',
            data:            data.map(d => d.revenu),
            borderColor:     COULEURS.orange,
            backgroundColor: 'rgba(193,68,14,0.12)',
            borderWidth:     2.5,
            pointBackgroundColor: COULEURS.warm,
            pointBorderColor:     COULEURS.warm,
            pointRadius:     5,
            pointHoverRadius:7,
            fill:            true,
            tension:         0.35,
          }]
        },
        options: optsBase()
      });
    })
    .catch(() => {});
}

/* ── 2. Top 5 produits (barres horizontales) ─────────────── */
function chargerTopProduits() {
  fetch('/api/dashboard/top-produits')
    .then(r => r.json())
    .then(data => {
      const ctx = document.getElementById('chart-top-produits');
      if (!ctx) return;
      detruireChart('top-produits');

      const couleurs = [COULEURS.orange, COULEURS.warm, COULEURS.green, COULEURS.blue, COULEURS.purple];

      _charts['top-produits'] = new Chart(ctx, {
        type: 'bar',
        data: {
          labels:   data.map(d => d.produit.length > 16 ? d.produit.slice(0,14)+'…' : d.produit),
          datasets: [{
            data:            data.map(d => d.revenus),
            backgroundColor: couleurs.slice(0, data.length),
            borderRadius:    6,
            borderSkipped:   false,
          }]
        },
        options: {
          ...optsBase(),
          indexAxis: 'y',
          scales: {
            x: {
              grid:  { color: 'rgba(255,255,255,0.04)', drawBorder: false },
              ticks: {
                color: '#A8A09A',
                callback: v => Math.round(v/1000) + 'k'
              },
              beginAtZero: true
            },
            y: {
              grid:  { display: false },
              ticks: { color: '#F0EAD6', font: { size: 11 } }
            }
          }
        }
      });
    })
    .catch(() => {});
}

/* ── 3. Répartition par société (donut) ──────────────────── */
function chargerRepartitionSocietes() {
  fetch('/api/dashboard/repartition-societes')
    .then(r => r.json())
    .then(data => {
      const ctx = document.getElementById('chart-societes');
      if (!ctx) return;
      detruireChart('societes');

      const labels  = data.map(d => d.societe);
      const valeurs = data.map(d => d.revenus);
      const bgCols  = labels.map(l => COULEURS_SOCIETES[l] || COULEURS.muted);

      _charts['societes'] = new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels,
          datasets: [{
            data:             valeurs,
            backgroundColor:  bgCols.map(c => c + 'CC'),
            borderColor:      bgCols,
            borderWidth:      2,
            hoverOffset:      6,
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          cutout: '60%',
          plugins: {
            legend: {
              display:  true,
              position: 'bottom',
              labels:   { color: '#A8A09A', font: { size: 11 }, padding: 10 }
            },
            tooltip: {
              backgroundColor: '#161628',
              borderColor:      'rgba(244,162,97,0.25)',
              borderWidth:      1,
              titleColor:       '#F4A261',
              bodyColor:        '#F0EAD6',
              padding:          10,
              cornerRadius:     8,
              callbacks: {
                label: ctx => {
                  const total = ctx.dataset.data.reduce((a,b) => a+b, 0);
                  const pct   = total > 0 ? Math.round(ctx.parsed / total * 100) : 0;
                  return ` ${formaterFCFA(ctx.parsed)}  (${pct}%)`;
                }
              }
            }
          }
        }
      });
    })
    .catch(() => {});
}

/* ── 4. Ventes par heure (caisse) ────────────────────────── */
function chargerGraphVentesHeure() {
  fetch('/api/ventes/par-heure')
    .then(r => r.json())
    .then(data => {
      const ctx = document.getElementById('chart-ventes-heure');
      if (!ctx) return;
      detruireChart('ventes-heure');

      _charts['ventes-heure'] = new Chart(ctx, {
        type: 'bar',
        data: {
          labels:   data.map(d => d.heure + 'h'),
          datasets: [{
            label:           'Ventes',
            data:            data.map(d => d.montant),
            backgroundColor: 'rgba(193,68,14,0.6)',
            borderColor:     COULEURS.orange,
            borderWidth:     1,
            borderRadius:    4,
            borderSkipped:   false,
          }]
        },
        options: optsBase()
      });
    })
    .catch(() => {});
}

/* ── 5. Stocks les plus bas (barres colorées) ────────────── */
function chargerGraphStocksBas() {
  fetch('/api/stocks/bas')
    .then(r => r.json())
    .then(data => {
      const ctx = document.getElementById('chart-stocks-bas');
      if (!ctx) return;
      detruireChart('stocks-bas');

      const bgCols = data.map(d => {
        if (d.quantite === 0)               return COULEURS.muted;
        if (d.quantite <= d.seuil_alerte/2) return COULEURS.red;
        if (d.quantite <= d.seuil_alerte)   return COULEURS.yellow;
        return COULEURS.green;
      });

      _charts['stocks-bas'] = new Chart(ctx, {
        type: 'bar',
        data: {
          labels:   data.map(d => d.nom.length > 14 ? d.nom.slice(0,12)+'…' : d.nom),
          datasets: [{
            data:            data.map(d => d.quantite),
            backgroundColor: bgCols,
            borderRadius:    4,
            borderSkipped:   false,
          }]
        },
        options: {
          ...optsBase(),
          plugins: {
            ...optsBase().plugins,
            tooltip: {
              ...optsBase().plugins.tooltip,
              callbacks: {
                label: ctx => ` Stock : ${ctx.parsed.y} unités`
              }
            }
          },
          scales: {
            x: {
              grid:  { display: false },
              ticks: { color: '#F0EAD6', font: { size: 11 }, maxRotation: 40 }
            },
            y: {
              grid:  { color: 'rgba(255,255,255,0.06)', drawBorder: false },
              ticks: { color: '#A8A09A' },
              beginAtZero: true
            }
          }
        }
      });
    })
    .catch(() => {});
}

/* ── 6. Dépenses approvisionnement (barres) ──────────────── */
function chargerGraphDepensesAppro() {
  fetch('/api/approvisionnements/depenses-semaine')
    .then(r => r.json())
    .then(data => {
      const ctx = document.getElementById('chart-depenses-appro');
      if (!ctx) return;
      detruireChart('depenses-appro');

      _charts['depenses-appro'] = new Chart(ctx, {
        type: 'bar',
        data: {
          labels:   data.map(d => d.date),
          datasets: [{
            label:           'Dépenses',
            data:            data.map(d => d.montant),
            backgroundColor: 'rgba(230,57,70,0.5)',
            borderColor:     COULEURS.red,
            borderWidth:     1,
            borderRadius:    4,
            borderSkipped:   false,
          }]
        },
        options: optsBase()
      });
    })
    .catch(() => {});
}

/* ── 7. Tendances par jour de semaine (barres) ───────────── */
function chargerTendancesJourSemaine() {
  fetch('/api/ml/tendances-semaine')
    .then(r => r.json())
    .then(data => {
      const ctx = document.getElementById('chart-jour-semaine');
      if (!ctx) return;
      detruireChart('jour-semaine');

      _charts['jour-semaine'] = new Chart(ctx, {
        type: 'bar',
        data: {
          labels:   data.map(d => d.jour),
          datasets: [{
            data:            data.map(d => d.revenu),
            backgroundColor: data.map((_, i) =>
              i === data.reduce((mi, d, i, a) => d.revenu > a[mi].revenu ? i : mi, 0)
                ? COULEURS.warm
                : 'rgba(193,68,14,0.5)'
            ),
            borderRadius:    5,
            borderSkipped:   false,
          }]
        },
        options: optsBase()
      });
    })
    .catch(() => {});
}

/* ── 8. Top produits consommés (barres horizontales) ─────── */
function chargerTopConsommes() {
  fetch('/api/ml/top-consommes')
    .then(r => r.json())
    .then(data => {
      const ctx = document.getElementById('chart-top-consommes');
      if (!ctx) return;
      detruireChart('top-consommes');

      const bgCols = data.map(d => COULEURS_SOCIETES[d.societe] || COULEURS.muted);

      _charts['top-consommes'] = new Chart(ctx, {
        type: 'bar',
        data: {
          labels:   data.map(d => d.produit.length > 16 ? d.produit.slice(0,14)+'…' : d.produit),
          datasets: [{
            data:            data.map(d => d.qte),
            backgroundColor: bgCols.map(c => c + 'BB'),
            borderColor:     bgCols,
            borderWidth:     1,
            borderRadius:    5,
            borderSkipped:   false,
          }]
        },
        options: {
          ...optsBase(),
          indexAxis: 'y',
          plugins: {
            ...optsBase().plugins,
            tooltip: {
              ...optsBase().plugins.tooltip,
              callbacks: { label: ctx => ` ${ctx.parsed.x} unités vendues` }
            }
          },
          scales: {
            x: {
              grid:  { color: 'rgba(255,255,255,0.04)', drawBorder: false },
              ticks: { color: '#A8A09A' },
              beginAtZero: true
            },
            y: {
              grid:  { display: false },
              ticks: { color: '#F0EAD6', font: { size: 11 } }
            }
          }
        }
      });
    })
    .catch(() => {});
}

/* ── 9. Prévision ML (ligne historique + prévision) ──────── */
let _chartPrevision = null;

function afficherGraphPrevision(historique, prevision) {
  const ctx = document.getElementById('chart-prevision');
  if (!ctx) return;
  detruireChart('prevision');

  const labelsHist = historique.map(d => d.date);
  const labelsPrev = prevision.map(d => d.date);
  const labelsAll  = [...labelsHist, ...labelsPrev];

  const dataHist = historique.map(d => d.revenu);
  const dataPrev = [
    ...new Array(historique.length - 1).fill(null),
    historique[historique.length - 1]?.revenu ?? null,
    ...prevision.map(d => d.revenu)
  ];
  const dataHaut = [
    ...new Array(historique.length - 1).fill(null),
    null,
    ...prevision.map(d => d.revenu_haut)
  ];
  const dataBas = [
    ...new Array(historique.length - 1).fill(null),
    null,
    ...prevision.map(d => d.revenu_bas)
  ];

  _charts['prevision'] = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labelsAll,
      datasets: [
        {
          label:           'Historique',
          data:            [...dataHist, ...new Array(labelsPrev.length).fill(null)],
          borderColor:     COULEURS.warm,
          backgroundColor: 'rgba(244,162,97,0.1)',
          borderWidth:     2.5,
          pointRadius:     4,
          pointBackgroundColor: COULEURS.warm,
          fill:            true,
          tension:         0.3,
          spanGaps:        false,
        },
        {
          label:           'Prévision',
          data:            dataPrev,
          borderColor:     COULEURS.orange,
          backgroundColor: 'transparent',
          borderWidth:     2,
          borderDash:      [6, 3],
          pointRadius:     4,
          pointBackgroundColor: COULEURS.orange,
          fill:            false,
          tension:         0.3,
          spanGaps:        false,
        },
        {
          label:           'Intervalle haut',
          data:            dataHaut,
          borderColor:     'transparent',
          backgroundColor: 'rgba(193,68,14,0.08)',
          borderWidth:     0,
          pointRadius:     0,
          fill:            '+1',
          tension:         0.3,
          spanGaps:        false,
        },
        {
          label:           'Intervalle bas',
          data:            dataBas,
          borderColor:     'transparent',
          backgroundColor: 'rgba(193,68,14,0.08)',
          borderWidth:     0,
          pointRadius:     0,
          fill:            false,
          tension:         0.3,
          spanGaps:        false,
        }
      ]
    },
    options: {
      ...optsBase(),
      plugins: {
        ...optsBase().plugins,
        legend: {
          display:  true,
          position: 'top',
          labels: {
            color:    '#A8A09A',
            filter:   item => !['Intervalle haut','Intervalle bas'].includes(item.text),
            font:     { size: 11 }
          }
        }
      }
    }
  });
}

/* ── 10. Évolution bilan (barres journalières) ───────────── */
function dessinerEvolutionBilan(donnees) {
  const ctx = document.getElementById('chart-bilan-evolution');
  if (!ctx) return;
  detruireChart('bilan-evolution');

  _charts['bilan-evolution'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels:   donnees.map(d => d.date),
      datasets: [{
        label:           'Revenus',
        data:            donnees.map(d => d.revenu),
        backgroundColor: 'rgba(193,68,14,0.6)',
        borderColor:     COULEURS.orange,
        borderWidth:     1,
        borderRadius:    4,
        borderSkipped:   false,
      }]
    },
    options: optsBase()
  });
}
// En fin de fichier
function chargerGraphiquesPage(page) {
    switch(page) {
        case 'index':
            chargerRevenusSemaine();
            chargerTopProduits();
            chargerRepartitionSocietes();
            chargerGraphStocksBas();
            break;
        case 'caisse':
            chargerGraphVentesHeure();
            break;
        case 'stocks':
            chargerGraphStocksBas();
            break;
        case 'appro':
            chargerGraphDepensesAppro();
            break;
        case 'tendances':
            chargerTendancesJourSemaine();
            chargerTopConsommes();
            // La prévision est chargée séparément via API ML
            break;
        case 'bilan':
            // Appelés après chargement des données
            break;
    }
}

/* ── 11. Donut bilan par société ─────────────────────────── */
function dessinerDonutBilan(donnees) {
  const ctx = document.getElementById('chart-bilan-societes');
  if (!ctx) return;
  detruireChart('bilan-societes');

  const labels  = donnees.map(d => d.societe);
  const valeurs = donnees.map(d => d.revenus);
  const bgCols  = labels.map(l => COULEURS_SOCIETES[l] || COULEURS.muted);

  _charts['bilan-societes'] = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data:            valeurs,
        backgroundColor: bgCols.map(c => c + 'CC'),
        borderColor:     bgCols,
        borderWidth:     2,
        hoverOffset:     6,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      cutout: '58%',
      plugins: {
        legend: {
          display:  true,
          position: 'bottom',
          labels:   { color: '#A8A09A', font: { size: 11 }, padding: 12 }
        },
        tooltip: {
          backgroundColor: '#161628',
          borderColor:      'rgba(244,162,97,0.25)',
          borderWidth:      1,
          titleColor:       '#F4A261',
          bodyColor:        '#F0EAD6',
          padding:          10,
          cornerRadius:     8,
          callbacks: {
            label: ctx => {
              const total = ctx.dataset.data.reduce((a,b) => a+b, 0);
              const pct   = total > 0 ? Math.round(ctx.parsed / total * 100) : 0;
              return ` ${formaterFCFA(ctx.parsed)}  (${pct}%)`;
            }
          }
        }
      }
    }
  });
}