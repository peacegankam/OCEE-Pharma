# routes/ventes.py - Routes pour l'enregistrement des ventes
from flask import Blueprint, jsonify, request, session
from database import get_db
from datetime import datetime, timedelta

ventes_bp = Blueprint('ventes', __name__)

@ventes_bp.route('/', methods=['POST'])
def enregistrer_vente():
    """Enregistre une ou plusieurs ventes (panier)"""
    try:
        data = request.get_json()
        
        if not data or 'ventes' not in data:
            return jsonify({'success': False, 'message': 'Données manquantes'}), 400
        
        ventes = data['ventes']  # Liste de {produit_id, quantite, prix_unitaire}
        
        conn = get_db()
        cursor = conn.cursor()
        
        total_vente = 0
        total_benefice = 0
        
        for vente in ventes:
            produit_id = vente['produit_id']
            quantite = vente['quantite']
            prix_unitaire = vente.get('prix_unitaire')  # Optionnel, sinon on prend le prix par défaut
            
            # Récupérer les infos produit
            cursor.execute('''
                SELECT p.nom, p.prix_achat, p.prix_vente, s.quantite as stock
                FROM produits p
                LEFT JOIN stocks s ON p.id = s.produit_id
                WHERE p.id = ?
            ''', (produit_id,))
            
            produit = cursor.fetchone()
            
            if not produit:
                conn.rollback()
                return jsonify({'success': False, 'message': f'Produit {produit_id} non trouvé'}), 400
            
            # Vérifier le stock
            if produit['stock'] < quantite:
                conn.rollback()
                return jsonify({
                    'success': False, 
                    'message': f'Stock insuffisant pour {produit["nom"]}. Disponible: {produit["stock"]}'
                }), 400
            
            # Utiliser le prix fourni ou le prix par défaut
            prix_final = prix_unitaire if prix_unitaire else produit['prix_vente']
            
            # Enregistrer la vente
            vendeur_id = session.get('user_id')
            date_actuelle = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO ventes (produit_id, quantite, prix_unitaire, vendeur_id, date_vente)
                VALUES (?, ?, ?, ?, ?)
            ''', (produit_id, quantite, prix_final, vendeur_id, date_actuelle))
            
            # Mettre à jour le stock
            cursor.execute('''
                UPDATE stocks 
                SET quantite = quantite - ?,
                    derniere_maj = ?
                WHERE produit_id = ?
            ''', (quantite, date_actuelle, produit_id))
            
            # Enregistrer dans l'historique
            cursor.execute('''
                INSERT INTO historique_stock 
                (produit_id, quantite_avant, quantite_apres, type, raison, date_mouvement)
                VALUES (?, ?, ?, 'vente', 'Vente en caisse', ?)
            ''', (produit_id, produit['stock'], produit['stock'] - quantite, date_actuelle))
            
            total_vente += quantite * prix_final
            total_benefice += quantite * (prix_final - produit['prix_achat'])
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'{len(ventes)} vente(s) enregistrée(s)',
            'total': total_vente,
            'benefice': total_benefice
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@ventes_bp.route('/aujourdhui', methods=['GET'])
def get_ventes_aujourdhui():
    """Retourne les ventes du jour avec KPIs"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        today = datetime.now().date()
        
        # Récupérer toutes les ventes du jour
        cursor.execute('''
            SELECT v.*, p.nom, p.societe, 
                   strftime('%H:%M', REPLACE(v.date_vente, 'T', ' ')) as heure
            FROM ventes v
            JOIN produits p ON v.produit_id = p.id
            WHERE DATE(REPLACE(v.date_vente, 'T', ' ')) = ?
            ORDER BY v.date_vente DESC
        ''', (today.isoformat(),))
        
        ventes = cursor.fetchall()
        
        # Calculer les totaux
        cursor.execute('''
            SELECT 
                COUNT(*) as nb_ventes,
                COALESCE(SUM(v.quantite * v.prix_unitaire), 0) as total,
                COALESCE(SUM(v.quantite * (v.prix_unitaire - p.prix_achat)), 0) as benefice
            FROM ventes v
            JOIN produits p ON v.produit_id = p.id
            WHERE DATE(REPLACE(v.date_vente, 'T', ' ')) = ?
        ''', (today.isoformat(),))
        
        totals = cursor.fetchone()
        conn.close()
        
        return jsonify({
            'success': True,
            'nb_ventes': totals['nb_ventes'],
            'total': totals['total'],
            'benefice': totals['benefice'],
            'ventes': [dict(v) for v in ventes]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@ventes_bp.route('/par-heure', methods=['GET'])
def get_ventes_par_heure():
    """Retourne les ventes groupées par heure pour aujourd'hui"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        today = datetime.now().date()
        
        # Créer une table des heures (0-23)
        heures = list(range(8, 24))  # 8h à 23h
        
        result = []
        for heure in heures:
            cursor.execute('''
                SELECT COALESCE(SUM(v.quantite * v.prix_unitaire), 0) as montant
                FROM ventes v
                WHERE DATE(REPLACE(v.date_vente, 'T', ' ')) = ? 
                AND strftime('%H', REPLACE(v.date_vente, 'T', ' ')) = ?
            ''', (today.isoformat(), f'{heure:02d}'))
            
            montant = cursor.fetchone()['montant']
            result.append({
                'heure': heure,
                'montant': montant
            })
        
        conn.close()
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@ventes_bp.route('/periode', methods=['GET'])
def get_ventes_periode():
    """Retourne les ventes sur une période donnée"""
    try:
        debut = request.args.get('debut')
        fin = request.args.get('fin')
        
        if not debut or not fin:
            return jsonify({'success': False, 'message': 'Paramètres debut et fin requis'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                DATE(REPLACE(v.date_vente, 'T', ' ')) as date,
                COUNT(*) as nb_ventes,
                COALESCE(SUM(v.quantite * v.prix_unitaire), 0) as total,
                COALESCE(SUM(v.quantite * (v.prix_unitaire - p.prix_achat)), 0) as benefice
            FROM ventes v
            JOIN produits p ON v.produit_id = p.id
            WHERE DATE(REPLACE(v.date_vente, 'T', ' ')) BETWEEN ? AND ?
            GROUP BY DATE(REPLACE(v.date_vente, 'T', ' '))
            ORDER BY date ASC
        ''', (debut, fin))
        
        result = cursor.fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'ventes': [dict(r) for r in result]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500