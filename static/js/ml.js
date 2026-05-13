/* ============================================================
   ml.js — Machine Learning, prévisions et recommandations
   Prophet-like, tendances, suggestions réapprovisionnement
   ============================================================ */

document.addEventListener('DOMContentLoaded', function() {
    // ========== ÉLÉMENTS DOM ==========
    // Contrôles
    const periodSelect = document.getElementById('ml-period');
    const generateBtn = document.getElementById('ml-generate-btn');
    const refreshBtn = document.getElementById('ml-refresh-btn');
    const exportBtn = document.getElementById('ml-export-btn');
    
    // Chargeurs
    const predictionLoader = document.getElementById('prediction-loader');
    const trendsLoader = document.getElementById('trends-loader');
    const productsLoader = document.getElementById('products-loader');
    
    // Graphiques (délégués à charts.js)
    const forecastChart = document.getElementById('forecastChart');
    const trendChart = document.getElementById('trendChart');
    const productChart = document.getElementById('productChart');
    
    // Conteneurs résultats
    const predictionSummary = document.getElementById('prediction-summary');
    const stockAdvice = document.getElementById('stock-advice');
    const trendsTable = document.getElementById('trends-table');
    const nextWeekTable = document.getElementById('next-week-table');
    
    // Insights textuels
    const insightBestDay = document.getElementById('insight-best-day');
    const insightGrowth = document.getElementById('insight-growth');
    const insightRisk = document.getElementById('insight-risk');
    
    // ========== ÉTAT ==========
    let currentPeriod = 7;
    let forecastData = null;
    let trendsData = null;
    let productsData = null;
    
    // ========== INITIALISATION ==========
    if (generateBtn) {
        generateBtn.addEventListener('click', () => {
            currentPeriod = periodSelect ? parseInt(periodSelect.value) : 7;
            generateAllPredictions();
        });
    }
    
    if (refreshBtn) {
        refreshBtn.addEventListener('click', retrainModels);
    }
    
    if (exportBtn) {
        exportBtn.addEventListener('click', exportPredictions);
    }
    
    if (periodSelect) {
        periodSelect.addEventListener('change', () => {
            currentPeriod = parseInt(periodSelect.value);
        });
    }
    
    // Chargement initial
    generateAllPredictions();
    
    // Rafraîchissement automatique toutes les 5 minutes
    setInterval(() => {
        if (document.visibilityState === 'visible') {
            generateAllPredictions(true); // silencieux
        }
    }, 300000);
    
    // ========== FONCTIONS PRINCIPALES ==========
    
    /**
     * Générer toutes les prédictions (ML complet)
     */
    function generateAllPredictions(silent = false) {
        if (!silent) {
            showLoaders();
        }
        
        // 1. Prévision globale
        fetch(`/api/ml/forecast?days=${currentPeriod}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    forecastData = data;
                    renderForecast(data);
                    updatePredictionSummary(data);
                } else {
                    if (!silent) afficherNotif('Erreur prévisions globales', 'error');
                }
            })
            .catch(() => {
                if (!silent) afficherNotif('Erreur réseau prévisions', 'error');
            })
            .finally(() => {
                if (!silent) hideLoader(predictionLoader);
            });
        
        // 2. Tendances par société
        fetch(`/api/ml/trends?days=${currentPeriod}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    trendsData = data;
                    renderTrends(data);
                    renderTrendsTable(data);
                }
            })
            .catch(() => {})
            .finally(() => {
                if (!silent) hideLoader(trendsLoader);
            });
        
        // 3. Produits stars et recommandations
        fetch(`/api/ml/products?days=${currentPeriod}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    productsData = data;
                    renderProducts(data);
                    renderStockAdvice(data);
                    updateInsights(data);
                }
            })
            .catch(() => {})
            .finally(() => {
                if (!silent) hideLoader(productsLoader);
            });
        
        // 4. Prévisions semaine prochaine
        fetch('/api/ml/next-week')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    renderNextWeekTable(data);
                }
            })
            .catch(() => {});
    }
    
    /**
     * Réentraîner les modèles ML
     */
    function retrainModels() {
        if (!confirm('Lancer un nouvel entraînement des modèles ? Cela peut prendre quelques secondes.')) {
            return;
        }
        
        showLoaders();
        
        fetch('/api/ml/retrain', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                afficherNotif('✅ Modèles entraînés avec succès', 'success');
                generateAllPredictions(true);
            } else {
                afficherNotif('Erreur entraînement: ' + data.message, 'error');
                hideAllLoaders();
            }
        })
        .catch(() => {
            afficherNotif('Erreur réseau', 'error');
            hideAllLoaders();
        });
    }
    
    /**
     * Afficher le graphique de prévision (utilise charts.js)
     */
    function renderForecast(data) {
        if (window.afficherGraphPrevision) {
            window.afficherGraphPrevision(data.historique, data.prevision);
        } else {
            console.warn('afficherGraphPrevision non disponible');
        }
    }
    
    /**
     * Afficher les tendances par société (délégué à charts.js)
     */
    function renderTrends(data) {
        if (window.chargerTendancesJourSemaine) {
            window.chargerTendancesJourSemaine();
        }
    }
    
    /**
     * Afficher les produits stars (délégué à charts.js)
     */
    function renderProducts(data) {
        if (window.chargerTopConsommes) {
            window.chargerTopConsommes();
        }
    }
    
    /**
     * Mettre à jour le résumé des prévisions
     */
    function updatePredictionSummary(data) {
        if (!predictionSummary) return;
        
        const lastHist = data.historique[data.historique.length - 1]?.revenu || 0;
        const nextForecast = data.prevision[0]?.revenu || 0;
        const variation = nextForecast - lastHist;
        const pctChange = lastHist > 0 ? ((variation / lastHist) * 100).toFixed(1) : 0;
        const trend = variation >= 0 ? 'hausse' : 'baisse';
        const trendClass = variation >= 0 ? 'text-success' : 'text-danger';
        
        let html = `
            <div class="prediction-summary">
                <div class="summary-item">
                    <span class="summary-label">Demain (prévision)</span>
                    <span class="summary-value">${formaterFCFA(nextForecast)}</span>
                </div>
                <div class="summary-item">
                    <span class="summary-label">Variation</span>
                    <span class="summary-value ${trendClass}">
                        ${variation >= 0 ? '+' : ''}${formaterFCFA(variation)} (${pctChange}%)
                    </span>
                </div>
                <div class="summary-item">
                    <span class="summary-label">Tendance</span>
                    <span class="summary-value">${trend === 'hausse' ? '📈' : '📉'} ${trend}</span>
                </div>
                <div class="summary-item">
                    <span class="summary-label">Intervalle</span>
                    <span class="summary-value">
                        ${formaterFCFA(data.prevision[0]?.revenu_bas)} – ${formaterFCFA(data.prevision[0]?.revenu_haut)}
                    </span>
                </div>
            </div>
        `;
        
        predictionSummary.innerHTML = html;
    }
    
    /**
     * Afficher le tableau des tendances par société
     */
    function renderTrendsTable(data) {
        if (!trendsTable) return;
        
        const tbody = trendsTable.querySelector('tbody') || trendsTable;
        
        if (!data.trends || !data.trends.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="table-empty">Données insuffisantes</td></tr>';
            return;
        }
        
        // Calculer la croissance pour chaque société
        const societes = data.trends.map(t => {
            const values = t.values;
            const avg = values.reduce((a, b) => a + b, 0) / values.length;
            const last = values[values.length - 1] || 0;
            const first = values[0] || 1;
            const growth = ((last - first) / first * 100).toFixed(1);
            
            return {
                nom: t.societe,
                couleur: getSocieteColor(t.societe),
                avg: avg,
                last: last,
                growth: growth,
                prediction: t.prediction || last * 1.05 // Simulation
            };
        });
        
        tbody.innerHTML = societes.map(s => {
            const growthClass = parseFloat(s.growth) >= 0 ? 'text-success' : 'text-danger';
            const growthIcon = parseFloat(s.growth) >= 0 ? '▲' : '▼';
            
            return `
                <tr>
                    <td><span class="color-dot" style="background: ${s.couleur}"></span> ${s.nom}</td>
                    <td>${formaterFCFA(s.avg)}</td>
                    <td class="${growthClass}">${growthIcon} ${Math.abs(s.growth)}%</td>
                    <td>${formaterFCFA(s.prediction)}</td>
                    <td>
                        <span class="badge ${parseFloat(s.growth) >= 5 ? 'badge-success' : parseFloat(s.growth) >= 0 ? 'badge-warning' : 'badge-danger'}">
                            ${parseFloat(s.growth) >= 5 ? '🔥 Forte hausse' : parseFloat(s.growth) >= 0 ? '📈 Stable' : '📉 Baisse'}
                        </span>
                    </td>
                </tr>
            `;
        }).join('');
    }
    
    /**
     * Afficher les prévisions pour la semaine prochaine
     */
    function renderNextWeekTable(data) {
        if (!nextWeekTable) return;
        
        const tbody = nextWeekTable.querySelector('tbody') || nextWeekTable;
        
        if (!data.jours || !data.jours.length) {
            tbody.innerHTML = '<tr><td colspan="4" class="table-empty">Prévisions non disponibles</td></tr>';
            return;
        }
        
        tbody.innerHTML = data.jours.map(j => {
            const jourClass = j.revenu > data.moyenne ? 'text-success' : '';
            const recommandation = j.revenu > data.moyenne ? '⚠️ Stock +' : '✓ Normal';
            
            return `
                <tr>
                    <td><strong>${j.nom}</strong></td>
                    <td class="${jourClass}">${formaterFCFA(j.revenu)}</td>
                    <td>${j.revenu_bas ? formaterFCFA(j.revenu_bas) : '—'}</td>
                    <td>${j.revenu_haut ? formaterFCFA(j.revenu_haut) : '—'}</td>
                    <td>${recommandation}</td>
                </tr>
            `;
        }).join('');
    }
    
    /**
     * Afficher les recommandations stock détaillées
     */
    function renderStockAdvice(data) {
        if (!stockAdvice) return;
        
        if (!data.advice || !data.advice.length) {
            stockAdvice.innerHTML = '<div class="empty-state">✅ Aucune recommandation pour le moment</div>';
            return;
        }
        
        let html = '<div class="advice-list">';
        
        data.advice.forEach(item => {
            const priorityClass = item.priorite === 'haute' ? 'advice-high' :
                                 item.priorite === 'moyenne' ? 'advice-medium' : 'advice-low';
            const daysLeft = item.stock_actuel / (item.consommation_journaliere || 1);
            const daysLeftText = daysLeft < 1 ? '⚠️ Aujourd\'hui' :
                                daysLeft < 3 ? `🔴 ${Math.ceil(daysLeft)} jours` :
                                daysLeft < 7 ? `🟡 ${Math.ceil(daysLeft)} jours` :
                                `✅ ${Math.ceil(daysLeft)} jours`;
            
            html += `
                <div class="advice-card ${priorityClass}">
                    <div class="advice-header">
                        <div class="advice-title">
                            <strong>${item.produit}</strong> 
                            <span class="badge-societe">${badgeSociete(item.societe)}</span>
                        </div>
                        <div class="advice-priority">${item.priorite === 'haute' ? '🔴 Urgent' : item.priorite === 'moyenne' ? '🟡 À surveiller' : '🟢 Normal'}</div>
                    </div>
                    
                    <div class="advice-stats">
                        <div class="stat-item">
                            <span class="stat-label">Stock actuel</span>
                            <span class="stat-value ${item.stock_actuel <= item.seuil_min ? 'text-danger' : ''}">${item.stock_actuel} unités</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Seuil minimum</span>
                            <span class="stat-value">${item.seuil_min}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Conso. journalière</span>
                            <span class="stat-value">${item.consommation_journaliere || '—'}/j</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">Autonomie</span>
                            <span class="stat-value">${daysLeftText}</span>
                        </div>
                    </div>
                    
                    <div class="progress-bar">
                        <div class="progress-fill ${item.stock_percent < 20 ? 'danger' : item.stock_percent < 40 ? 'warning' : 'success'}" 
                             style="width: ${Math.min(100, item.stock_percent)}%"></div>
                    </div>
                    
                    <div class="advice-message">${item.message}</div>
                    
                    <div class="advice-actions">
                        <button onclick="window.location.href='/appro?product=${item.produit_id}'" class="btn-primary btn-small">
                            📦 Commander
                        </button>
                        <button onclick="window.location.href='/stocks?ajuster=${item.produit_id}'" class="btn-ghost btn-small">
                            ⚡ Ajuster
                        </button>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        stockAdvice.innerHTML = html;
    }
    
    /**
     * Mettre à jour les insights textuels
     */
    function updateInsights(data) {
        if (!insightBestDay || !insightGrowth || !insightRisk) return;
        
        // Meilleur jour
        if (data.best_day) {
            insightBestDay.innerHTML = `
                <strong>${data.best_day.nom}</strong> avec ${formaterFCFA(data.best_day.moyenne)} en moyenne
            `;
        }
        
        // Croissance
        if (data.growth) {
            const growthClass = data.growth.taux >= 0 ? 'text-success' : 'text-danger';
            insightGrowth.innerHTML = `
                <span class="${growthClass}">${data.growth.taux >= 0 ? '📈 +' : '📉 '}${Math.abs(data.growth.taux)}%</span> 
                sur les ${data.growth.periode} derniers jours
            `;
        }
        
        // Risques
        if (data.risks && data.risks.length) {
            insightRisk.innerHTML = data.risks.map(r => `
                <div class="risk-item">
                    <span class="risk-icon">${r.niveau === 'haut' ? '🔴' : r.niveau === 'moyen' ? '🟡' : '🟢'}</span>
                    <span>${r.message}</span>
                </div>
            `).join('');
        } else {
            insightRisk.innerHTML = '<span class="text-success">✅ Aucun risque détecté</span>';
        }
    }
    
    /**
     * Exporter les prévisions en PDF
     */
    function exportPredictions() {
        if (!forecastData) {
            afficherNotif('Générez d\'abord des prévisions', 'warning');
            return;
        }
        
        afficherNotif('Préparation de l\'export...', 'info');
        
        fetch('/api/ml/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                forecast: forecastData,
                trends: trendsData,
                products: productsData,
                period: currentPeriod
            })
        })
        .then(response => response.blob())
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `previsions_pharma_${new Date().toISOString().split('T')[0]}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            afficherNotif('Export terminé', 'success');
        })
        .catch(() => afficherNotif('Erreur export', 'error'));
    }
    
    // ========== UTILITAIRES ==========
    
    function showLoaders() {
        if (predictionLoader) predictionLoader.style.display = 'block';
        if (trendsLoader) trendsLoader.style.display = 'block';
        if (productsLoader) productsLoader.style.display = 'block';
    }
    
    function hideAllLoaders() {
        if (predictionLoader) predictionLoader.style.display = 'none';
        if (trendsLoader) trendsLoader.style.display = 'none';
        if (productsLoader) productsLoader.style.display = 'none';
    }
    
    function hideLoader(loader) {
        if (loader) loader.style.display = 'none';
    }
    
    function getSocieteColor(societe) {
        const colors = {
            'Antibiotiques': '#2A9D8F',
            'Analgésiques': '#E76F51',
            'Vitamines': '#F4A261',
            'Dermatologie': '#E9C46A',
            'Matériel Médical': '#264653'
        };
        return colors[societe] || '#A8A09A';
    }
    
    // Exposer certaines fonctions globalement
    window.generateAllPredictions = generateAllPredictions;
    window.retrainModels = retrainModels;
    window.exportPredictions = exportPredictions;
});