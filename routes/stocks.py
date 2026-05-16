# routes/stocks.py - Routes pour la gestion des stocks
from flask import Blueprint, jsonify, request
from database import get_db
from datetime import datetime, timedelta

stocks_bp = Blueprint('stocks', __name__)

@stocks_bp.route('/', methods=['GET'])
def get_stocks():
    """Retourne tous les stocks avec infos produits"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                p.id, p.nom, p.societe, p.prix_achat, p.prix_vente,
                p.seuil_alerte, s.quantite,
                (s.quantite * p.prix_achat) as valeur
            FROM produits p
            LEFT JOIN stocks s ON p.id = s.produit_id
            ORDER BY 
                CASE 
                    WHEN s.quantite <= p.seuil_alerte/2 THEN 1
                    WHEN s.quantite <= p.seuil_alerte THEN 2
                    ELSE 3
                END,
                s.quantite ASC
        ''')
        
        stocks = cursor.fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'stocks': [dict(s) for s in stocks]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@stocks_bp.route('/global', methods=['GET'])
def get_stocks_global():
    """Retourne les KPIs globaux des stocks"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Nombre total de produits
        cursor.execute('SELECT COUNT(*) as count FROM produits')
        total_produits = cursor.fetchone()['count']
        
        # Valeur totale du stock
        cursor.execute('''
            SELECT COALESCE(SUM(s.quantite * p.prix_achat), 0) as total
            FROM stocks s
            JOIN produits p ON s.produit_id = p.id
        ''')
        valeur_totale = cursor.fetchone()['total']
        
        # Produits en alerte
        cursor.execute('''
            SELECT COUNT(*) as count
            FROM stocks s
            JOIN produits p ON s.produit_id = p.id
            WHERE s.quantite <= p.seuil_alerte
        ''')
        en_alerte = cursor.fetchone()['count']
        
        # Produits en rupture
        cursor.execute('''
            SELECT COUNT(*) as count
            FROM stocks s
            WHERE s.quantite = 0
        ''')
        en_rupture = cursor.fetchone()['count']
        
        conn.close()
        
        return jsonify({
            'success': True,
            'total_produits': total_produits,
            'valeur_totale': valeur_totale,
            'en_alerte': en_alerte,
            'en_rupture': en_rupture
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@stocks_bp.route('/bas', methods=['GET'])
def get_stocks_bas():
    """Retourne les 15 produits avec le stock le plus bas"""
    try:
        limit = request.args.get('limit', 15, type=int)
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                p.id, p.nom, p.societe, p.seuil_alerte,
                s.quantite,
                (s.quantite * 100.0 / NULLIF(p.seuil_alerte, 0)) as stock_percent
            FROM stocks s
            JOIN produits p ON s.produit_id = p.id
            WHERE s.quantite <= p.seuil_alerte * 2
            ORDER BY s.quantite ASC
            LIMIT ?
        ''', (limit,))
        
        stocks = cursor.fetchall()
        conn.close()
        
        return jsonify([dict(s) for s in stocks])
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@stocks_bp.route('/check/<int:produit_id>', methods=['GET'])
def check_stock(produit_id):
    """Vérifie si une quantité est disponible"""
    try:
        quantite = request.args.get('quantite', 1, type=int)
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT quantite FROM stocks WHERE produit_id = ?
        ''', (produit_id,))
        
        stock = cursor.fetchone()
        conn.close()
        
        if not stock:
            return jsonify({'success': False, 'message': 'Produit non trouvé'}), 404
        
        disponible = stock['quantite'] >= quantite
        
        return jsonify({
            'success': True,
            'disponible': disponible,
            'stock': stock['quantite']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@stocks_bp.route('/ajuster', methods=['POST'])
def ajuster_stock():
    """Ajuste manuellement le stock d'un produit"""
    try:
        data = request.get_json()
        
        required = ['produit_id', 'quantite', 'type']
        for field in required:
            if field not in data:
                return jsonify({'success': False, 'message': f'Champ manquant: {field}'}), 400
        
        produit_id = data['produit_id']
        quantite = data['quantite']
        type_ajust = data['type']  # 'ajout' ou 'retrait'
        raison = data.get('raison', 'Ajustement manuel')
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Récupérer le stock actuel
        cursor.execute('SELECT quantite FROM stocks WHERE produit_id = ?', (produit_id,))
        stock_actuel = cursor.fetchone()
        # Si la ligne de stock n'existe pas encore, la créer (ancien=0)
        if not stock_actuel:
            ancien = 0
        else:
            ancien = stock_actuel['quantite']

        if type_ajust == 'ajout':
            nouveau = ancien + quantite
        else:  # retrait
            if ancien < quantite:
                return jsonify({'success': False, 'message': 'Stock insuffisant pour le retrait'}), 400
            nouveau = ancien - quantite
        
        # Mettre à jour ou insérer le stock
        date_actuelle = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if stock_actuel:
            cursor.execute('''
                UPDATE stocks 
                SET quantite = ?, derniere_maj = ?
                WHERE produit_id = ?
            ''', (nouveau, date_actuelle, produit_id))
        else:
            cursor.execute('''
                INSERT INTO stocks (produit_id, quantite, derniere_maj)
                VALUES (?, ?, ?)
            ''', (produit_id, nouveau, date_actuelle))
        
        # Enregistrer dans l'historique
        from flask import session
        utilisateur_id = session.get('user_id')
        cursor.execute('''
            INSERT INTO historique_stock 
            (produit_id, quantite_avant, quantite_apres, type, raison, date_mouvement, utilisateur_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (produit_id, ancien, nouveau, type_ajust, raison, date_actuelle, utilisateur_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Stock ajusté avec succès',
            'ancien': ancien,
            'nouveau': nouveau
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@stocks_bp.route('/alertes', methods=['GET'])
def get_alertes():
    """Retourne toutes les alertes stock"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                p.id as produit_id,
                p.nom as produit,
                p.societe,
                s.quantite as stock_actuel,
                p.seuil_alerte as seuil_min,
                CASE 
                    WHEN s.quantite = 0 THEN 'critique'
                    WHEN s.quantite <= p.seuil_alerte/2 THEN 'critique'
                    WHEN s.quantite <= p.seuil_alerte THEN 'faible'
                    ELSE 'ok'
                END as niveau,
                CASE 
                    WHEN s.quantite = 0 THEN '🔴 RUPTURE - Commander d\'urgence'
                    WHEN s.quantite <= p.seuil_alerte/2 THEN '🔴 Stock critique - Commander immédiatement'
                    WHEN s.quantite <= p.seuil_alerte THEN '⚠️ Stock faible - Prévoir commande'
                    ELSE '✅ Stock OK'
                END as message
            FROM stocks s
            JOIN produits p ON s.produit_id = p.id
            WHERE s.quantite <= p.seuil_alerte
            ORDER BY 
                CASE 
                    WHEN s.quantite = 0 THEN 1
                    WHEN s.quantite <= p.seuil_alerte/2 THEN 2
                    ELSE 3
                END,
                s.quantite ASC
        ''')
        
        alertes = cursor.fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'alertes': [dict(a) for a in alertes]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@stocks_bp.route('/alertes-count', methods=['GET'])
def get_alertes_count():
    """Retourne le nombre d'alertes (pour le badge header)"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) as count
            FROM stocks s
            JOIN produits p ON s.produit_id = p.id
            WHERE s.quantite <= p.seuil_alerte
        ''')
        
        count = cursor.fetchone()['count']
        conn.close()
        
        return jsonify({'success': True, 'count': count})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@stocks_bp.route('/historique', methods=['GET'])
def get_historique():
    """Retourne l'historique des mouvements de stock"""
    try:
        filtre = request.args.get('filtre', 'tous')
        periode = request.args.get('periode', 7, type=int)
        
        conn = get_db()
        cursor = conn.cursor()
        
        date_limite = (datetime.now() - timedelta(days=periode)).date()
        
        query = '''
            SELECT 
                h.*,
                p.nom as produit,
                p.societe,
                u.nom as auteur_nom,
                u.role as auteur_role
            FROM historique_stock h
            JOIN produits p ON h.produit_id = p.id
            LEFT JOIN utilisateurs u ON h.utilisateur_id = u.id
            WHERE DATE(h.date_mouvement) >= ?
        '''
        params = [date_limite.isoformat()]
        
        if filtre != 'tous':
            query += ' AND h.type = ?'
            params.append(filtre)
        
        query += ' ORDER BY h.date_mouvement DESC LIMIT 100'
        
        cursor.execute(query, params)
        historique = cursor.fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'mouvements': [dict(h) for h in historique]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500