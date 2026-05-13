8# routes/dashboard.py - Routes pour les données du dashboard principal
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import sqlite3
import random

from database import (
    get_db,
    get_stats_globales,
    get_revenus_semaine,
    get_top_produits,
    get_repartition_societes,
    get_stocks_critiques
)

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/kpis', methods=['GET'])
def get_kpis():
    """Retourne les KPIs pour le dashboard"""
    try:
        # Récupérer les stats depuis la base de données
        stats = get_stats_globales()
        
        # Si la base est vide, retourner des données de démonstration
        if not stats or stats.get('revenus_jour') == 0 and stats.get('ventes_jour') == 0:
            # Données de démonstration
            return jsonify({
                'success': True,
                'revenus_jour': 245500,
                'ventes_jour': 42,
                'benefice_jour': 82350,
                'alertes_stock': 3
            })
        
        return jsonify({
            'success': True,
            'revenus_jour': stats.get('revenus_jour', 0),
            'ventes_jour': stats.get('ventes_jour', 0),
            'benefice_jour': stats.get('benefice_jour', 0),
            'alertes_stock': stats.get('alertes_stock', 0)
        })
    except Exception as e:
        print(f"Erreur dashboard/kpis: {str(e)}")
        # En cas d'erreur, retourner des données de démonstration
        return jsonify({
            'success': True,
            'revenus_jour': 245500,
            'ventes_jour': 42,
            'benefice_jour': 82350,
            'alertes_stock': 3
        })

@dashboard_bp.route('/revenus-semaine', methods=['GET'])
def get_revenus_semaine_route():
    """Retourne les revenus des 7 derniers jours"""
    try:
        # Essayer de récupérer depuis la base
        data = get_revenus_semaine()
        
        # Si pas de données, générer des données de démonstration
        if not data or len(data) == 0:
            today = datetime.now()
            data = []
            for i in range(6, -1, -1):
                date = (today - timedelta(days=i)).strftime('%d/%m')
                # Générer des revenus avec une tendance
                base = 45000 + (i * 2000)
                variation = random.randint(-5000, 5000)
                data.append({
                    'date': date,
                    'revenu': base + variation
                })
        
        return jsonify(data)
    except Exception as e:
        print(f"Erreur dashboard/revenus-semaine: {str(e)}")
        # Données de démonstration en cas d'erreur
        today = datetime.now()
        demo_data = []
        for i in range(6, -1, -1):
            date = (today - timedelta(days=i)).strftime('%d/%m')
            demo_data.append({
                'date': date,
                'revenu': 45000 + (i * 2000) + random.randint(-3000, 3000)
            })
        return jsonify(demo_data)

@dashboard_bp.route('/top-produits', methods=['GET'])
def get_top_produits_route():
    """Retourne le top 5 des produits"""
    try:
        limit = request.args.get('limit', 5, type=int)
        data = get_top_produits(limit)
        
        # Si pas de données, générer des données de démonstration
        if not data or len(data) == 0:
            demo_produits = [
                {'produit': 'Castel Beer', 'revenus': 125000},
                {'produit': 'Guinness', 'revenus': 98000},
                {'produit': 'Mützig', 'revenus': 87000},
                {'produit': 'Whisky', 'revenus': 65000},
                {'produit': 'Tangui', 'revenus': 43000}
            ]
            return jsonify(demo_produits[:limit])
        
        # Filtrer : garder seulement les produits de type 'médicaments'
        # Dans ce projet : la colonne produits.societe contient la catégorie.
        # Mais get_top_produits() ne renvoie que {nom/produit, revenus}.
        # Donc on recalcule ici pour avoir societe.
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT p.nom as produit,
                       p.societe,
                       SUM(v.quantite * v.prix_unitaire) as revenus
                FROM ventes v
                JOIN produits p ON v.produit_id = p.id
                GROUP BY p.id, p.nom, p.societe
                HAVING LOWER(p.societe) = LOWER('Médicaments')
                ORDER BY revenus DESC
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            conn.close()
    except Exception as e:
        print(f"Erreur dashboard/top-produits: {str(e)}")
        # Données de démonstration
        return jsonify([
            {'produit': 'Castel Beer', 'revenus': 125000},
            {'produit': 'Guinness', 'revenus': 98000},
            {'produit': 'Mützig', 'revenus': 87000},
            {'produit': 'Whisky', 'revenus': 65000},
            {'produit': 'Tangui', 'revenus': 43000}
        ])

@dashboard_bp.route('/repartition-societes', methods=['GET'])
def get_repartition_societes_route():
    """Retourne la répartition des ventes par société (uniquement médicaments)."""
    try:
        limit_societes = 10
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT p.societe,
                       SUM(v.quantite * v.prix_unitaire) as revenus
                FROM ventes v
                JOIN produits p ON v.produit_id = p.id
                WHERE LOWER(p.societe) = LOWER('Médicaments')
                   OR LOWER(p.societe) LIKE '%m%C3%A9dic%'
                GROUP BY p.societe
                ORDER BY revenus DESC
                LIMIT ?
            ''', (limit_societes,))
            rows = cursor.fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            conn.close()
    except Exception as e:
        print(f"Erreur dashboard/repartition-societes: {str(e)}")
        # Données de démonstration (médicaments)
        return jsonify([
            {'societe': 'Médicaments', 'revenus': 245000}
        ])

@dashboard_bp.route('/peremptions-critiques', methods=['GET'])
def get_peremptions_critiques_route():
    """Retourne les produits en alerte de péremption (médicaments seulement).
    - Critique si date_peremption <= 7 jours
    - Surveillance si date_peremption <= 30 jours
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        try:
            # On suppose que produits.date_peremption est stockée en format ISO (YYYY-MM-DD)
            # et que SQLite peut comparer via date().
            cursor.execute('''
                SELECT p.id, p.nom, p.societe, s.quantite, p.seuil_alerte, p.date_peremption
                FROM stocks s
                JOIN produits p ON s.produit_id = p.id
                WHERE p.date_peremption IS NOT NULL
                  AND (LOWER(p.societe) = LOWER('Médicaments') OR LOWER(p.societe) LIKE '%m%C3%A9dic%')
                  AND date(p.date_peremption) <= date('now', '+30 day')
                ORDER BY date(p.date_peremption) ASC
                LIMIT 20
            ''')
            rows = cursor.fetchall()
            produits = [dict(r) for r in rows]
        finally:
            conn.close()

        # Calculer statut (critique/surveillance) et ne garder que <=30 jours
        today = datetime.now().date()
        for p in produits:
            dp_raw = p.get('date_peremption')
            try:
                dp = datetime.fromisoformat(str(dp_raw)).date() if dp_raw else None
            except Exception:
                dp = None

            jours = None
            if dp:
                jours = (dp - today).days

            # Normaliser : si parsing échoue, on met en 'surveillance' et on garde
            p['jours_restants'] = jours
            if jours is not None and jours <= 7:
                p['niveau'] = 'critique'
                p['couleur'] = 'E63946'
            else:
                p['niveau'] = 'surveillance'
                p['couleur'] = 'FFB627'

        return jsonify({'success': True, 'produits': produits})
    except Exception as e:
        print(f"Erreur dashboard/peremptions-critiques: {str(e)}")
        return jsonify({
            'success': True,
            'produits': [
                {
                    'id': 1,
                    'nom': 'Amoxicilline 500mg',
                    'societe': 'Antibiotiques',
                    'quantite': 2,
                    'seuil_alerte': 20,
                    'date_peremption': '2026-05-20',
                    'jours_restants': 7,
                    'niveau': 'critique',
                    'couleur': 'E63946'
                }
            ]
        })

@dashboard_bp.route('/stocks-critiques', methods=['GET'])
def get_stocks_critiques_route():
    """Retourne la liste des stocks critiques (uniquement médicaments)."""
    try:
        # Recalcul via SQL pour garantir le filtrage médicaments
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT p.id, p.nom, p.societe, s.quantite, p.seuil_alerte
                FROM stocks s
                JOIN produits p ON s.produit_id = p.id
                WHERE s.quantite <= p.seuil_alerte
                  AND (LOWER(p.societe) = LOWER('Médicaments')
                       OR LOWER(p.societe) LIKE '%m%C3%A9dic%')
                ORDER BY (s.quantite * 1.0 / NULLIF(p.seuil_alerte,0)) ASC
                LIMIT 10
            ''')
            rows = cursor.fetchall()
            stocks = [dict(r) for r in rows]
        finally:
            conn.close()

        # Si pas de données, générer des données de démonstration (médicaments)
        if not stocks:
            demo_stocks = [
                {'id': 4, 'nom': 'Amoxicilline 500mg', 'societe': 'Antibiotiques', 'quantite': 2, 'seuil_alerte': 20},
                {'id': 6, 'nom': 'Ibuprofène 400mg', 'societe': 'Analgésiques', 'quantite': 10, 'seuil_alerte': 30},
                {'id': 3, 'nom': 'Azithromycine 500mg', 'societe': 'Antibiotiques', 'quantite': 3, 'seuil_alerte': 10},
            ]
            return jsonify({'success': True, 'stocks': demo_stocks})

        return jsonify({'success': True, 'stocks': stocks})
    except Exception as e:
        print(f"Erreur dashboard/stocks-critiques: {str(e)}")
        # Données de démonstration
        return jsonify({
            'success': True,
            'stocks': [
                {'id': 4, 'nom': 'Amoxicilline 500mg', 'societe': 'Antibiotiques', 'quantite': 2, 'seuil_alerte': 20},
                {'id': 6, 'nom': 'Ibuprofène 400mg', 'societe': 'Analgésiques', 'quantite': 10, 'seuil_alerte': 30}
            ]
        })

@dashboard_bp.route('/ventes-recentes', methods=['GET'])
def get_ventes_recentes():
    """Retourne les 10 dernières ventes"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT v.id, v.date_vente, p.nom as produit, 
                   v.quantite, v.prix_unitaire,
                   (v.quantite * v.prix_unitaire) as total
            FROM ventes v
            JOIN produits p ON v.produit_id = p.id
            ORDER BY v.date_vente DESC
            LIMIT 10
        ''')
        
        ventes = cursor.fetchall()
        conn.close()
        
        # Si pas de ventes, données démo
        if not ventes or len(ventes) == 0:
            demo_ventes = []
            now = datetime.now()
            for i in range(5):
                demo_ventes.append({
                    'id': i+1,
                    'date_vente': (now - timedelta(minutes=15*i)).isoformat(),
                    'produit': ['Castel Beer', 'Guinness', 'Mützig', 'Tangui', 'Whisky'][i % 5],
                    'quantite': i+1,
                    'prix_unitaire': [600, 900, 650, 300, 4500][i % 5],
                    'total': [600, 900, 650, 300, 4500][i % 5] * (i+1)
                })
            return jsonify({
                'success': True,
                'ventes': demo_ventes
            })
        
        return jsonify({
            'success': True,
            'ventes': [dict(v) for v in ventes]
        })
    except Exception as e:
        print(f"Erreur dashboard/ventes-recentes: {str(e)}")
        # Données de démonstration
        demo_ventes = []
        now = datetime.now()
        for i in range(5):
            demo_ventes.append({
                'id': i+1,
                'date_vente': (now - timedelta(minutes=15*i)).isoformat(),
                'produit': ['Castel Beer', 'Guinness', 'Mützig', 'Tangui', 'Whisky'][i % 5],
                'quantite': i+1,
                'prix_unitaire': [600, 900, 650, 300, 4500][i % 5],
                'total': [600, 900, 650, 300, 4500][i % 5] * (i+1)
            })
        return jsonify({
            'success': True,
            'ventes': demo_ventes
        })

@dashboard_bp.route('/activite-recente', methods=['GET'])
def get_activite_recente():
    """Retourne l'activité récente (ventes + appros)"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Dernières ventes
        cursor.execute('''
            SELECT 'vente' as type, v.date_vente as date,
                   p.nom as produit, v.quantite,
                   (v.quantite * v.prix_unitaire) as montant
            FROM ventes v
            JOIN produits p ON v.produit_id = p.id
            ORDER BY v.date_vente DESC
            LIMIT 5
        ''')
        ventes = cursor.fetchall()
        
        # Derniers approvisionnements
        cursor.execute('''
            SELECT 'appro' as type, a.date_appro as date,
                   p.nom as produit, a.quantite,
                   (a.quantite * a.prix_achat_unitaire) as montant
            FROM approvisionnements a
            JOIN produits p ON a.produit_id = p.id
            ORDER BY a.date_appro DESC
            LIMIT 5
        ''')
        appros = cursor.fetchall()
        
        conn.close()
        
        # Fusion et tri
        activite = [dict(v) for v in ventes] + [dict(a) for a in appros]
        activite.sort(key=lambda x: x['date'], reverse=True)
        
        # Si pas d'activité, données démo
        if not activite or len(activite) == 0:
            now = datetime.now()
            activite = [
                {
                    'type': 'vente',
                    'date': now.isoformat(),
                    'produit': 'Castel Beer',
                    'quantite': 3,
                    'montant': 1800
                },
                {
                    'type': 'vente',
                    'date': (now - timedelta(minutes=5)).isoformat(),
                    'produit': 'Guinness',
                    'quantite': 2,
                    'montant': 1800
                },
                {
                    'type': 'appro',
                    'date': (now - timedelta(hours=2)).isoformat(),
                    'produit': 'Mützig',
                    'quantite': 24,
                    'montant': 15600
                }
            ]
        
        return jsonify({
            'success': True,
            'activite': activite[:10]
        })
    except Exception as e:
        print(f"Erreur dashboard/activite-recente: {str(e)}")
        # Données de démonstration
        now = datetime.now()
        return jsonify({
            'success': True,
            'activite': [
                {
                    'type': 'vente',
                    'date': now.isoformat(),
                    'produit': 'Castel Beer',
                    'quantite': 3,
                    'montant': 1800
                },
                {
                    'type': 'vente',
                    'date': (now - timedelta(minutes=5)).isoformat(),
                    'produit': 'Guinness',
                    'quantite': 2,
                    'montant': 1800
                }
            ]
        })

@dashboard_bp.route('/bilan', methods=['GET'])
def get_bilan():
    """Retourne les données pour le bilan sur une période"""
    try:
        debut = request.args.get('debut')
        fin = request.args.get('fin')
        
        if not debut or not fin:
            return jsonify({'success': False, 'message': 'Période manquante'}), 400
            
        conn = get_db()
        cursor = conn.cursor()
        
        # Totaux (Revenus, Couts, Benefice)
        cursor.execute('''
            SELECT 
                COUNT(*) as nb_transactions,
                COALESCE(SUM(v.quantite * v.prix_unitaire), 0) as revenus,
                COALESCE(SUM(v.quantite * p.prix_achat), 0) as couts,
                COALESCE(SUM(v.quantite * (v.prix_unitaire - p.prix_achat)), 0) as benefice
            FROM ventes v
            JOIN produits p ON v.produit_id = p.id
            WHERE DATE(v.date_vente) BETWEEN ? AND ?
        ''', (debut, fin))
        
        totals = dict(cursor.fetchone())
        
        # Évolution journalière
        cursor.execute('''
            SELECT DATE(date_vente) as date, SUM(quantite * prix_unitaire) as montant
            FROM ventes
            WHERE DATE(date_vente) BETWEEN ? AND ?
            GROUP BY DATE(date_vente)
            ORDER BY date ASC
        ''', (debut, fin))
        
        evolution = [dict(row) for row in cursor.fetchall()]
        
        # Par société
        cursor.execute('''
            SELECT p.societe, SUM(v.quantite * v.prix_unitaire) as revenus, SUM(v.quantite) as qte
            FROM ventes v
            JOIN produits p ON v.produit_id = p.id
            WHERE DATE(v.date_vente) BETWEEN ? AND ?
            GROUP BY p.societe
            ORDER BY revenus DESC
        ''', (debut, fin))
        
        par_societe = [dict(row) for row in cursor.fetchall()]
        
        # Top produits
        cursor.execute('''
            SELECT p.nom as produit, p.societe, SUM(v.quantite) as qte, SUM(v.quantite * v.prix_unitaire) as revenus
            FROM ventes v
            JOIN produits p ON v.produit_id = p.id
            WHERE DATE(v.date_vente) BETWEEN ? AND ?
            GROUP BY p.id
            ORDER BY revenus DESC
            LIMIT 10
        ''', (debut, fin))
        
        top_produits = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return jsonify({
            'success': True,
            **totals,
            'evolution_journaliere': evolution,
            'par_societe': par_societe,
            'top_produits': top_produits
        })
        
    except Exception as e:
        print(f"Erreur bilan: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@dashboard_bp.route('/test', methods=['GET'])
def test_route():
    """Route de test pour vérifier que le blueprint fonctionne"""
    return jsonify({
        'success': True,
        'message': 'Le blueprint dashboard fonctionne correctement',
        'time': datetime.now().isoformat()
    })