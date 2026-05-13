# routes/appro.py - Routes pour les approvisionnements
from flask import Blueprint, jsonify, request, session
from database import get_db
from datetime import datetime, timedelta

appro_bp = Blueprint('appro', __name__)


@appro_bp.route('/', methods=['POST'])
def enregistrer_appro():
    """Enregistre un nouvel approvisionnement"""
    try:
        data = request.get_json()
        
        required = ['produit_id', 'quantite', 'prix_achat_unitaire']
        for field in required:
            if field not in data:
                return jsonify({'success': False, 'message': f'Champ manquant: {field}'}), 400
        
        produit_id = data['produit_id']
        quantite = data['quantite']
        prix_achat = data['prix_achat_unitaire']
        note = data.get('note', '')
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Vérifier que le produit existe
        cursor.execute('SELECT * FROM produits WHERE id = ?', (produit_id,))
        produit = cursor.fetchone()
        
        if not produit:
            return jsonify({'success': False, 'message': 'Produit non trouvé'}), 404

        # Récupérer le stock actuel + seuil
        cursor.execute('SELECT quantite FROM stocks WHERE produit_id = ?', (produit_id,))
        stock_actuel = cursor.fetchone()

        ancien_stock = stock_actuel['quantite'] if stock_actuel else 0
        seuil_alerte = produit['seuil_alerte'] if 'seuil_alerte' in produit.keys() else None
        date_actuelle = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Option: gérant seul pour créer/valider une livraison
        # si le produit est en rupture/alerte (stock actuel <= seuil d'alerte).
        # Employés: peuvent consulter, mais pas valider la livraison en cas d'alerte.
        est_role_admin = (session.get('role') == 'admin')
        en_alerte = False
        if seuil_alerte is not None:
            en_alerte = (ancien_stock is not None and ancien_stock <= seuil_alerte)
        else:
            en_alerte = (ancien_stock == 0)

        if (not est_role_admin) and en_alerte:
            return jsonify({
                'success': False,
                'message': "Action réservée au gérant : livraison pour produit en rupture/alerte (stock <= seuil)."
            }), 403


        
        # Enregistrer l'approvisionnement
        cursor.execute('''
            INSERT INTO approvisionnements 
            (produit_id, quantite, prix_achat_unitaire, note, date_appro)
            VALUES (?, ?, ?, ?, ?)
        ''', (produit_id, quantite, prix_achat, note, date_actuelle))
        
        # Mettre à jour le stock
        if stock_actuel:
            cursor.execute('''
                UPDATE stocks 
                SET quantite = quantite + ?,
                    derniere_maj = ?
                WHERE produit_id = ?
            ''', (quantite, date_actuelle, produit_id))
        else:
            cursor.execute('''
                INSERT INTO stocks (produit_id, quantite, derniere_maj)
                VALUES (?, ?, ?)
            ''', (produit_id, quantite, date_actuelle))
        
        # Enregistrer dans l'historique
        cursor.execute('''
            INSERT INTO historique_stock 
            (produit_id, quantite_avant, quantite_apres, type, raison, date_mouvement)
            VALUES (?, ?, ?, 'appro', ?, ?)
        ''', (produit_id, ancien_stock, ancien_stock + quantite, note or 'Approvisionnement', date_actuelle))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Approvisionnement enregistré avec succès',
            'nouveau_stock': ancien_stock + quantite
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@appro_bp.route('/historique', methods=['GET'])
def get_historique_appro():
    """Retourne l'historique des approvisionnements"""
    try:
        periode = request.args.get('periode', 30, type=int)
        
        conn = get_db()
        cursor = conn.cursor()
        
        date_limite = (datetime.now() - timedelta(days=periode)).date()
        
        cursor.execute('''
            SELECT 
                a.*,
                p.nom as produit,
                p.societe,
                (a.quantite * a.prix_achat_unitaire) as total
            FROM approvisionnements a
            JOIN produits p ON a.produit_id = p.id
            WHERE DATE(a.date_appro) >= ?
            ORDER BY a.date_appro DESC
        ''', (date_limite.isoformat(),))
        
        appros = cursor.fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'approvisionnements': [dict(a) for a in appros]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@appro_bp.route('/depenses-semaine', methods=['GET'])
def get_depenses_semaine():
    """Retourne les dépenses d'approvisionnement des 7 derniers jours"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        dates = []
        depenses = []
        
        for i in range(6, -1, -1):
            date = (datetime.now() - timedelta(days=i)).date()
            dates.append(date.strftime('%d/%m'))
            
            cursor.execute('''
                SELECT COALESCE(SUM(quantite * prix_achat_unitaire), 0) as total
                FROM approvisionnements
                WHERE DATE(date_appro) = ?
            ''', (date.isoformat(),))
            
            depenses.append(cursor.fetchone()['total'])
        
        conn.close()
        
        return jsonify([{'date': d, 'montant': m} for d, m in zip(dates, depenses)])
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@appro_bp.route('/stats', methods=['GET'])
def get_stats_appro():
    """Retourne les statistiques des approvisionnements"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Total dépenses 30 derniers jours
        date_limite = (datetime.now() - timedelta(days=30)).date()
        
        cursor.execute('''
            SELECT 
                COUNT(*) as nb_appro,
                COALESCE(SUM(quantite * prix_achat_unitaire), 0) as total_depenses,
                COALESCE(SUM(quantite), 0) as total_articles
            FROM approvisionnements
            WHERE DATE(date_appro) >= ?
        ''', (date_limite.isoformat(),))
        
        stats = cursor.fetchone()
        
        # Top produits approvisionnés
        cursor.execute('''
            SELECT 
                p.nom,
                SUM(a.quantite) as total_quantite,
                SUM(a.quantite * a.prix_achat_unitaire) as total_depense
            FROM approvisionnements a
            JOIN produits p ON a.produit_id = p.id
            WHERE DATE(a.date_appro) >= ?
            GROUP BY a.produit_id
            ORDER BY total_depense DESC
            LIMIT 5
        ''', (date_limite.isoformat(),))
        
        top = cursor.fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'nb_appro': stats['nb_appro'],
            'total_depenses': stats['total_depenses'],
            'total_articles': stats['total_articles'],
            'top_produits': [dict(t) for t in top]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500