# Analyse de la Structure de la Base de Données pour implémenter le FIFO

## 📋 État Actuel de la Structure

### Tables Existantes Pertinentes:

```sql
-- Table stocks (stock actuel par produit)
CREATE TABLE stocks (
    produit_id INTEGER PRIMARY KEY,
    quantite INTEGER NOT NULL DEFAULT 0,
    derniere_maj TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table approvisionnements (historique des achats)
CREATE TABLE approvisionnements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produit_id INTEGER NOT NULL,
    quantite INTEGER NOT NULL,
    prix_achat_unitaire INTEGER NOT NULL,
    date_appro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    note TEXT
);

-- Table ventes (historique des ventes)
CREATE TABLE ventes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produit_id INTEGER NOT NULL,
    quantite INTEGER NOT NULL,
    prix_unitaire INTEGER NOT NULL,
    date_vente TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    vendeur_id INTEGER
);

-- Table historique_stock (mouvements de stock)
CREATE TABLE historique_stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produit_id INTEGER NOT NULL,
    quantite_avant INTEGER NOT NULL,
    quantite_apres INTEGER NOT NULL,
    type VARCHAR(50) NOT NULL,
    raison TEXT,
    date_mouvement TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🔍 Analyse FIFO

### Problème Principal: ❌
**La structure actuelle NE supporte PAS le FIFO.**

Raisons:
1. **Pas de suivi du lot d'approvisionnement** - Les approvisionnements sont enregistrés, mais pas liés aux ventes
2. **Pas de date de péremption par lot** - La date de péremption est au niveau du produit, pas du lot
3. **Pas d'ordre de consommation** - Les ventes ne savent pas quel lot elles consomment
4. **Stock global uniquement** - La table `stocks` ne maintient que la quantité totale par produit

### Exemple du Problème:
```
Produit: Amoxicilline 500mg

Approvisionnements:
- 15/05/2026: 100 unités à 1500 FCFA → Péremption: 15/01/2027
- 16/05/2026: 50 unités à 1400 FCFA → Péremption: 16/02/2027
Total stock: 150 unités

Vente de 30 unités le 17/05/2026:
- Avec FIFO: 30 unités du lot du 15/05 (plus proche de péremption)
- Sans FIFO: ??? (on ne sait pas quel lot vendre)
```

---

## ✅ Solutions Recommandées

### SOLUTION 1: Ajouter des Colonnes à `stocks` (Minimaliste)

**Avantages**: Simple, peu de changements
**Inconvénients**: Gère un seul lot à la fois

```sql
ALTER TABLE stocks ADD COLUMN (
    date_peremption_lot DATE,
    date_appro_lot TIMESTAMP,
    lote_id INTEGER
);
```

**Implémentation**: FIFO très basique, problématique pour multi-lots

---

### SOLUTION 2: Table `stocks_par_lot` (Recommandée) ⭐

**Avantages**: FIFO complet, traçabilité parfaite, péremption par lot
**Inconvénients**: Refactorisation nécessaire des ventes

```sql
-- Créer une table intermédiaire pour les lots
CREATE TABLE lots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produit_id INTEGER NOT NULL,
    date_appro TIMESTAMP NOT NULL,
    date_peremption DATE,
    quantite_initiale INTEGER NOT NULL,
    quantite_consommee INTEGER DEFAULT 0,
    quantite_disponible INTEGER NOT NULL,
    prix_achat_unitaire INTEGER NOT NULL,
    fournisseur VARCHAR(255),
    numero_batch VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (produit_id) REFERENCES produits(id)
);

-- Modifier les ventes pour tracer le lot
ALTER TABLE ventes ADD COLUMN (
    lot_id INTEGER,
    FOREIGN KEY (lot_id) REFERENCES lots(id)
);

-- Indice pour performances
CREATE INDEX idx_lots_produit ON lots(produit_id, date_peremption, date_appro);
CREATE INDEX idx_ventes_lot ON ventes(lot_id);
```

**Algorithme FIFO pour vente**:
```sql
-- Récupérer le lot le plus ancien (FIFO) avec stock disponible
SELECT id, quantite_disponible 
FROM lots 
WHERE produit_id = ? 
  AND quantite_disponible > 0
ORDER BY date_peremption ASC, date_appro ASC
LIMIT 1;

-- Mettre à jour après consommation
UPDATE lots 
SET quantite_consommee = quantite_consommee + ?,
    quantite_disponible = quantite_disponible - ?
WHERE id = ?;
```

---

### SOLUTION 3: Table `stocks_mouvements` (Très Avancée)

**Avantages**: Traçabilité complète, audit trail parfait
**Inconvénients**: Plus complexe, plus de stockage

```sql
CREATE TABLE stocks_mouvements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produit_id INTEGER NOT NULL,
    lot_id INTEGER,
    type_mouvement VARCHAR(50), -- 'appro', 'vente', 'retour', 'ajustement'
    quantite INTEGER NOT NULL,
    prix_unitaire INTEGER,
    date_mouvement TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reference_doc VARCHAR(100), -- Numéro vente/appro
    utilisateur_id INTEGER,
    notes TEXT,
    FOREIGN KEY (produit_id) REFERENCES produits(id),
    FOREIGN KEY (lot_id) REFERENCES lots(id)
);
```

---

## 📊 Comparaison des Solutions

| Critère | Actuelle | Sol. 1 | Sol. 2 ⭐ | Sol. 3 |
|---------|----------|--------|----------|--------|
| **Complexité** | Très simple | Simple | Moyen | Élevée |
| **FIFO Support** | ❌ Non | Partiel | ✅ Complet | ✅ Complet |
| **Multi-lots** | ❌ Non | ❌ Non | ✅ Oui | ✅ Oui |
| **Péremption/lot** | ❌ Non | Partiel | ✅ Oui | ✅ Oui |
| **Traçabilité** | Faible | Faible | Bonne | Excellente |
| **Performance** | Rapide | Rapide | Bonne | Acceptable |
| **Refactor Code** | - | Faible | Moyenne | Grande |

---

## 🎯 Recommandation Finale

**→ SOLUTION 2 (Table `lots`) est RECOMMANDÉE**

### Raisons:
1. ✅ Support complet du FIFO
2. ✅ Gestion de la péremption par lot (critique pour pharma)
3. ✅ Traçabilité par lot
4. ✅ Bon équilibre complexité/fonctionnalité
5. ✅ Extensible pour futures améliorations

### Étapes d'Implémentation:

#### Phase 1: Structure BD
```sql
-- Créer la table lots
CREATE TABLE lots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produit_id INTEGER NOT NULL,
    date_appro TIMESTAMP NOT NULL,
    date_peremption DATE NOT NULL,
    quantite_initiale INTEGER NOT NULL,
    quantite_consommee INTEGER DEFAULT 0,
    prix_achat_unitaire INTEGER NOT NULL,
    numero_batch VARCHAR(100),
    FOREIGN KEY (produit_id) REFERENCES produits(id)
);

-- Ajouter lot_id à ventes
ALTER TABLE ventes ADD COLUMN lot_id INTEGER;
ALTER TABLE ventes ADD FOREIGN KEY (lot_id) REFERENCES lots(id);

-- Ajouter lot_id à approvisionnements
ALTER TABLE approvisionnements ADD COLUMN lot_id INTEGER;
```

#### Phase 2: Migration des Données
```sql
-- Créer un lot pour chaque approvisionnement existant
INSERT INTO lots (produit_id, date_appro, date_peremption, quantite_initiale, prix_achat_unitaire)
SELECT 
    produit_id,
    date_appro,
    produits.date_peremption,
    quantite,
    prix_achat_unitaire
FROM approvisionnements
JOIN produits ON approvisionnements.produit_id = produits.id;
```

#### Phase 3: Fonctions FIFO
```python
# Python: routes/stocks.py

def consommer_stock_fifo(produit_id, quantite_demandee):
    """Consomme le stock en respectant le FIFO (lots les plus anciens)"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Récupérer les lots par ordre FIFO
    cursor.execute('''
        SELECT id, quantite_initiale - COALESCE(SUM(v.quantite), 0) as quantite_disponible
        FROM lots l
        LEFT JOIN ventes v ON l.id = v.lot_id
        WHERE l.produit_id = ? AND l.quantite_disponible > 0
        GROUP BY l.id
        ORDER BY l.date_peremption ASC, l.date_appro ASC
    ''', (produit_id,))
    
    lots_consommes = []
    quantite_restante = quantite_demandee
    
    for lot in cursor.fetchall():
        lot_id = lot['id']
        disponible = lot['quantite_disponible']
        quantite_a_consommer = min(disponible, quantite_restante)
        
        lots_consommes.append({
            'lot_id': lot_id,
            'quantite': quantite_a_consommer
        })
        
        quantite_restante -= quantite_a_consommer
        if quantite_restante == 0:
            break
    
    if quantite_restante > 0:
        raise ValueError(f"Stock insuffisant: {quantite_restante} unités manquantes")
    
    return lots_consommes
```

#### Phase 4: Interface de Vente Modifiée
- Afficher le lot consommé lors de la vente
- Afficher la date de péremption du lot
- Option pour forcer un lot spécifique

---

## 📝 SQL pour Vérifier l'État FIFO

```sql
-- Voir tous les lots avec leur stock restant
SELECT 
    l.id,
    p.nom,
    l.numero_batch,
    l.date_appro,
    l.date_peremption,
    l.quantite_initiale,
    COALESCE(SUM(v.quantite), 0) as quantite_vendue,
    l.quantite_initiale - COALESCE(SUM(v.quantite), 0) as quantite_disponible
FROM lots l
JOIN produits p ON l.produit_id = p.id
LEFT JOIN ventes v ON l.id = v.lot_id
GROUP BY l.id
ORDER BY l.date_peremption ASC, l.date_appro ASC;

-- Alertes de péremption
SELECT 
    p.nom,
    l.numero_batch,
    l.date_peremption,
    l.quantite_disponible,
    CAST((julianday(l.date_peremption) - julianday('now')) AS INTEGER) as jours_restants
FROM lots l
JOIN produits p ON l.produit_id = p.id
WHERE l.date_peremption <= date('now', '+30 days')
  AND l.quantite_disponible > 0
ORDER BY l.date_peremption ASC;
```

---

## ⚠️ Points d'Attention Critiques pour Pharma

1. **Légalité**: Certains pays exigent le FIFO/FEFO pour les médicaments
2. **Traçabilité**: Audits réguliers necessaires
3. **Péremption**: Gestion stricte des dates limite
4. **Rappels**: Capacité à retirer un lot complètement
5. **Rapports**: Audit trail complet par lot

---

## 🚀 Plan d'Action

**Court terme (1-2 semaines)**:
- ✅ Phase 1: Créer la structure `lots`
- ✅ Phase 2: Migrer les données
- ✅ Phase 3: Implémenter les fonctions FIFO

**Moyen terme (2-4 semaines)**:
- Modifier l'interface de vente
- Tester le FIFO en production
- Former les utilisateurs

**Long terme**:
- Ajouter des reports FIFO
- Alertes automats de péremption
- Intégration FIFO/FEFO strict
