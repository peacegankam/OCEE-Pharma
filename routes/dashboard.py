8# routes/dashboard.py - Routes pour les données du dashboard principal
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import sqlite3
import random

from database import (
    get_db,
    get_stats_globales,
    get_revenus_semaine,
    get_revenus_mensuel,
    get_revenus_total,
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
        
        # Calculer le nombre d'alertes (stock + péremption)
        conn = get_db()
        cursor = conn.cursor()
        
        # Alertes stock critiques
        cursor.execute('''
            SELECT COUNT(*) as count
            FROM stocks s
            JOIN produits p ON s.produit_id = p.id
            WHERE s.quantite <= p.seuil_alerte
        ''')
        row = cursor.fetchone()
        alertes_stock = row['count'] if row else 0
        
        # Alertes péremption critiques (< 7 jours)
        cursor.execute('''
            SELECT COUNT(*) as count
            FROM produits p
            WHERE p.date_peremption IS NOT NULL
            AND date(p.date_peremption) <= date('now', '+7 day')
            AND date(p.date_peremption) >= date('now')
        ''')
        row = cursor.fetchone()
        alertes_peremption = row['count'] if row else 0
        
        conn.close()
        
        total_alertes = alertes_stock + alertes_peremption
        
        return jsonify({
            'success': True,
            'revenus_jour': stats.get('revenus_jour', 0),
            'ventes_jour': stats.get('ventes_jour', 0),
            'benefice_jour': stats.get('benefice_jour', 0),
            'alertes_stock': total_alertes,
            'revenus_mensuel': get_revenus_mensuel(),
            'revenus_total': get_revenus_total()
        })
    except Exception as e:
        print(f"Erreur dashboard/kpis: {str(e)}")
        return jsonify({
            'success': True,
            'revenus_jour': 0,
            'ventes_jour': 0,
            'benefice_jour': 0,
            'alertes_stock': 0
        })

@dashboard_bp.route('/revenus-semaine', methods=['GET'])
def get_revenus_semaine_route():
    """Retourne les revenus des 7 derniers jours"""
    try:
        data = get_revenus_semaine()
        return jsonify(data)
    except Exception as e:
        print(f"Erreur dashboard/revenus-semaine: {str(e)}")
        return jsonify([])

@dashboard_bp.route('/top-produits', methods=['GET'])
def get_top_produits_route():
    """Retourne le top 5 des produits par revenus"""
    try:
        limit = request.args.get('limit', 5, type=int)
        
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT p.id,
                       p.nom as produit,
                       p.societe,
                       SUM(v.quantite) as quantite_vendue,
                       SUM(v.quantite * v.prix_unitaire) as revenus
                FROM ventes v
                JOIN produits p ON v.produit_id = p.id
                GROUP BY p.id, p.nom, p.societe
                ORDER BY revenus DESC
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            data = [dict(r) for r in rows]
        finally:
            conn.close()
        
        return jsonify(data)
    except Exception as e:
        print(f"Erreur dashboard/top-produits: {str(e)}")
        return jsonify([])

@dashboard_bp.route('/repartition-societes', methods=['GET'])
def get_repartition_societes_route():
    """Retourne la répartition des ventes par société."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT p.societe,
                       SUM(v.quantite * v.prix_unitaire) as revenus,
                       COUNT(*) as nombre_ventes
                FROM ventes v
                JOIN produits p ON v.produit_id = p.id
                GROUP BY p.societe
                ORDER BY revenus DESC
                LIMIT 10
            ''')
            rows = cursor.fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            conn.close()
    except Exception as e:
        print(f"Erreur dashboard/repartition-societes: {str(e)}")
        return jsonify([])

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
        return jsonify({'success': False, 'produits': []})

@dashboard_bp.route('/stocks-critiques', methods=['GET'])
def get_stocks_critiques_route():
    """Retourne la liste des stocks critiques et alertes de péremption."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        alertes = []
        
        # 1. Ruptures de stock (quantité = 0)
        try:
            cursor.execute('''
                SELECT p.id, p.nom, p.societe, s.quantite, p.seuil_alerte
                FROM stocks s
                JOIN produits p ON s.produit_id = p.id
                WHERE s.quantite = 0
            ''')
            rows = cursor.fetchall()
            for r in rows:
                alertes.append({
                    'id': r['id'], 'nom': r['nom'], 'societe': r['societe'],
                    'quantite': 0, 'seuil_alerte': r['seuil_alerte'],
                    'type_alerte': 'rupture', 'niveau': 'critique',
                    'message': 'RUPTURE DE STOCK'
                })
        except Exception as e: print(f"Erreur ruptures: {e}")

        # 2. Stocks critiques (0 < quantité <= seuil)
        try:
            cursor.execute('''
                SELECT p.id, p.nom, p.societe, s.quantite, p.seuil_alerte
                FROM stocks s
                JOIN produits p ON s.produit_id = p.id
                WHERE s.quantite > 0 AND s.quantite <= p.seuil_alerte
            ''')
            rows = cursor.fetchall()
            for r in rows:
                alertes.append({
                    'id': r['id'], 'nom': r['nom'], 'societe': r['societe'],
                    'quantite': r['quantite'], 'seuil_alerte': r['seuil_alerte'],
                    'type_alerte': 'stock_critique', 'niveau': 'warning',
                    'message': f"Stock faible: {r['quantite']} unités"
                })
        except Exception as e: print(f"Erreur stocks bas: {e}")

        # 3. Péremptions (périmés ou dans moins de 30 jours)
        try:
            cursor.execute('''
                SELECT p.id, p.nom, p.societe, p.date_peremption, s.quantite
                FROM produits p
                JOIN stocks s ON p.id = s.produit_id
                WHERE p.date_peremption IS NOT NULL
                AND date(p.date_peremption) <= date('now', '+30 day')
            ''')
            rows = cursor.fetchall()
            today = datetime.now().date()
            for r in rows:
                dp = datetime.fromisoformat(str(r['date_peremption'])).date()
                jours = (dp - today).days
                if jours < 0:
                    niveau, msg = 'critique', f"PÉRIMÉ ({abs(jours)}j)"
                elif jours <= 7:
                    niveau, msg = 'warning', f"Périme dans {jours}j"
                else:
                    niveau, msg = 'faible', f"Périme dans {jours}j"
                
                alertes.append({
                    'id': r['id'], 'nom': r['nom'], 'societe': r['societe'],
                    'quantite': r['quantite'], 'seuil_alerte': 0, 
                    'date_peremption': str(r['date_peremption']), 'jours_restants': jours,
                    'type_alerte': 'peremption', 'niveau': niveau,
                    'message': msg
                })
        except Exception as e: print(f"Erreur peremptions: {e}")

        conn.close()
        
        # Tri : critique d'abord, puis warning, puis faible
        ordre = {'critique': 0, 'warning': 1, 'faible': 2}
        alertes.sort(key=lambda x: (ordre.get(x.get('niveau'), 3), x.get('type_alerte')))
        
        return jsonify({'success': True, 'stocks': alertes[:25]})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

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
        
        if not ventes or len(ventes) == 0:
            return jsonify({'success': True, 'ventes': []})
            
        return jsonify({
            'success': True,
            'ventes': [dict(v) for v in ventes]
        })
    except Exception as e:
        print(f"Erreur dashboard/ventes-recentes: {str(e)}")
        return jsonify({'success': False, 'ventes': []})

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
        
        if not activite or len(activite) == 0:
            return jsonify({'success': True, 'activite': []})
            
        return jsonify({
            'success': True,
            'activite': activite[:10]
        })
    except Exception as e:
        print(f"Erreur dashboard/activite-recente: {str(e)}")
        return jsonify({'success': False, 'activite': []})

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
            WHERE DATE(REPLACE(v.date_vente, 'T', ' ')) BETWEEN ? AND ?
        ''', (debut, fin))
        
        totals = dict(cursor.fetchone())
        
        # Évolution journalière
        cursor.execute('''
            SELECT DATE(REPLACE(date_vente, 'T', ' ')) as date, SUM(quantite * prix_unitaire) as montant
            FROM ventes
            WHERE DATE(REPLACE(date_vente, 'T', ' ')) BETWEEN ? AND ?
            GROUP BY DATE(REPLACE(date_vente, 'T', ' '))
            ORDER BY date ASC
        ''', (debut, fin))
        
        evolution = [dict(row) for row in cursor.fetchall()]
        
        # Par société
        cursor.execute('''
            SELECT p.societe, SUM(v.quantite * v.prix_unitaire) as revenus, SUM(v.quantite) as qte
            FROM ventes v
            JOIN produits p ON v.produit_id = p.id
            WHERE DATE(REPLACE(v.date_vente, 'T', ' ')) BETWEEN ? AND ?
            GROUP BY p.societe
            ORDER BY revenus DESC
        ''', (debut, fin))
        
        par_societe = [dict(row) for row in cursor.fetchall()]
        
        # Top produits
        cursor.execute('''
            SELECT p.nom as produit, p.societe, SUM(v.quantite) as qte, SUM(v.quantite * v.prix_unitaire) as revenus
            FROM ventes v
            JOIN produits p ON v.produit_id = p.id
            WHERE DATE(REPLACE(v.date_vente, 'T', ' ')) BETWEEN ? AND ?
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