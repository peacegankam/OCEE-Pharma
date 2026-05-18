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
                p.id,
                p.nom,
                p.societe,
                p.seuil_alerte,
                COALESCE(s.quantite, 0) as quantite,
                COALESCE(
                    SUM(l.quantite_actuelle * l.prix_achat_unitaire) / NULLIF(SUM(l.quantite_actuelle), 0),
                    0
                ) as prix_achat,
                COALESCE(MAX(l.prix_vente_unitaire), 0) as prix_vente,
                COALESCE(SUM(l.quantite_actuelle * l.prix_achat_unitaire), 0) as valeur
            FROM produits p
            LEFT JOIN stocks s ON p.id = s.produit_id
            LEFT JOIN lots_stock l ON p.id = l.produit_id AND l.quantite_actuelle > 0
            GROUP BY p.id
            ORDER BY 
                CASE 
                    WHEN quantite <= COALESCE(p.seuil_alerte, 0)/2 THEN 1
                    WHEN quantite <= COALESCE(p.seuil_alerte, 0) THEN 2
                    ELSE 3
                END,
                quantite ASC
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
            SELECT COALESCE(SUM(l.quantite_actuelle * l.prix_achat_unitaire), 0) as total
            FROM lots_stock l
            WHERE l.quantite_actuelle > 0
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

def get_lots_details_str(cursor, produit_id):
    cursor.execute('''
        SELECT date_reception, date_peremption, quantite_actuelle 
        FROM lots_stock 
        WHERE produit_id = ? AND quantite_actuelle > 0 
        ORDER BY date_reception DESC
    ''', (produit_id,))
    lots = cursor.fetchall()
    details = []
    for lot in lots:
        dt_raw = lot['date_reception']
        dt_str = '—'
        if dt_raw:
            try:
                if isinstance(dt_raw, str):
                    dt_str = datetime.strptime(dt_raw[:10], '%Y-%m-%d').strftime('%d/%m/%Y')
                else:
                    dt_str = dt_raw.strftime('%d/%m/%Y')
            except Exception:
                dt_str = str(dt_raw)[:10]
        details.append(f"{dt_str} {lot['quantite_actuelle']}")
    return "\n".join(details)

@stocks_bp.route('/ajuster', methods=['POST'])
def ajuster_stock():
    """Ajuste manuellement le stock d'un produit (retrait d'anomalie, casse, péremption)"""
    try:
        data = request.get_json()
        
        required = ['produit_id', 'raison']
        for field in required:
            if field not in data:
                return jsonify({'success': False, 'message': f'Champ manquant: {field}'}), 400
        
        produit_id = data['produit_id']
        raison = data['raison']
        quantite = int(data.get('quantite', 0))
        
        if raison not in ['Retrait produit périmé', 'Casse', 'Correction inventaire négatif']:
            return jsonify({'success': False, 'message': 'Motif invalide'}), 400

        if raison != 'Retrait produit périmé' and quantite <= 0:
            return jsonify({'success': False, 'message': 'La quantité doit être strictement positive'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM produits WHERE id = ?', (produit_id,))
        produit = cursor.fetchone()
        if not produit:
            conn.close()
            return jsonify({'success': False, 'message': 'Produit non trouvé'}), 404

        cursor.execute('SELECT quantite FROM stocks WHERE produit_id = ?', (produit_id,))
        stock_actuel = cursor.fetchone()
        ancien = stock_actuel['quantite'] if stock_actuel else 0

        stock_initial_details = get_lots_details_str(cursor, produit_id)
        perte_financiere = 0
        date_actuelle = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        today_str = datetime.now().date().isoformat()
        cursor.execute('''
            SELECT * FROM lots_stock
            WHERE produit_id = ? AND quantite_actuelle > 0
            ORDER BY 
                CASE WHEN date_peremption < ? THEN 0 ELSE 1 END ASC,
                date_reception ASC
        ''', (produit_id, today_str))
        lots = cursor.fetchall()

        if raison == 'Retrait produit périmé':
            cursor.execute('''
                SELECT * FROM lots_stock
                WHERE produit_id = ? AND quantite_actuelle > 0 AND date_peremption < ?
                ORDER BY date_peremption ASC, date_reception ASC
            ''', (produit_id, today_str))
            lots_perimes = cursor.fetchall()
            total_perimes = sum(l['quantite_actuelle'] for l in lots_perimes)

            if total_perimes == 0:
                conn.close()
                return jsonify({'success': False, 'message': 'Aucun lot périmé à retirer'}), 400

            quantite = total_perimes
            restant = quantite
            for lot in lots_perimes:
                if restant <= 0:
                    break
                disponible = lot['quantite_actuelle']
                preleve = min(disponible, restant)
                perte_financiere += preleve * lot['prix_achat_unitaire']
                cursor.execute('UPDATE lots_stock SET quantite_actuelle = quantite_actuelle - ? WHERE id = ?', (preleve, lot['id']))
                restant -= preleve

        else:
            total_disponible = sum(l['quantite_actuelle'] for l in lots)
            if total_disponible < quantite:
                conn.close()
                return jsonify({'success': False, 'message': 'Stock insuffisant pour le retrait'}), 400

            restant = quantite
            for lot in lots:
                if restant <= 0:
                    break
                disponible = lot['quantite_actuelle']
                preleve = min(disponible, restant)
                perte_financiere += preleve * lot['prix_achat_unitaire']
                cursor.execute('UPDATE lots_stock SET quantite_actuelle = quantite_actuelle - ? WHERE id = ?', (preleve, lot['id']))
                restant -= preleve

        nouveau = max(0, ancien - quantite)
        if stock_actuel:
            cursor.execute('UPDATE stocks SET quantite = ?, derniere_maj = ? WHERE produit_id = ?', (nouveau, date_actuelle, produit_id))
        else:
            cursor.execute('INSERT INTO stocks (produit_id, quantite, derniere_maj) VALUES (?, ?, ?)', (produit_id, nouveau, date_actuelle))

        stock_final_details = get_lots_details_str(cursor, produit_id)
        utilisateur_id = session.get('user_id')

        cursor.execute('''
            INSERT INTO historique_stock 
            (produit_id, quantite_avant, quantite_apres, type, raison, date_mouvement, utilisateur_id,
             stock_initial_details, stock_final_details, perte_financiere)
            VALUES (?, ?, ?, 'retrait', ?, ?, ?, ?, ?, ?)
        ''', (produit_id, ancien, nouveau, raison, date_actuelle, utilisateur_id,
              stock_initial_details, stock_final_details, perte_financiere))

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Stock ajusté avec succès',
            'ancien': ancien,
            'nouveau': nouveau,
            'perte_financiere': perte_financiere
        })
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return jsonify({'success': False, 'message': str(e)}), 500

@stocks_bp.route('/expired-lots/<int:produit_id>', methods=['GET'])
def get_lots_perimes(produit_id):
    """Retourne les lots périmés disponibles pour un produit"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        today_str = datetime.now().date().isoformat()
        cursor.execute('''
            SELECT id, quantite_initiale, quantite_actuelle, prix_achat_unitaire, date_reception, date_peremption, reference_lot
            FROM lots_stock
            WHERE produit_id = ? AND quantite_actuelle > 0 AND date_peremption < ?
            ORDER BY date_peremption ASC, date_reception ASC
        ''', (produit_id, today_str))
        lots = cursor.fetchall()
        total_perimes = sum(l['quantite_actuelle'] for l in lots)
        conn.close()

        return jsonify({
            'success': True,
            'lots_perimes': [dict(l) for l in lots],
            'total_perimes': total_perimes
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
        periode = request.args.get('periode', 365, type=int)
        
        conn = get_db()
        cursor = conn.cursor()
        
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
            WHERE 1=1
        '''
        params = []
        
        if periode and periode > 0:
            date_limite = (datetime.now() - timedelta(days=periode)).date()
            query += ' AND DATE(h.date_mouvement) >= ?'
            params.append(date_limite.isoformat())
        
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