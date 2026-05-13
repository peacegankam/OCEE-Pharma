# routes/produits.py - Routes pour la gestion des produits
from flask import Blueprint, jsonify, request
from database import get_db
from datetime import datetime
from config import SOCIETES

produits_bp = Blueprint('produits', __name__)

@produits_bp.route('/', methods=['GET'])
def get_produits():
    """Retourne tous les produits (avec ou sans stock)"""
    try:
        with_stock = request.args.get('with_stock', 'false').lower() == 'true'
        societe_filter = request.args.get('societe')
        
        conn = get_db()
        cursor = conn.cursor()
        
        query = '''
            SELECT p.*, s.quantite as stock_actuel
            FROM produits p
            LEFT JOIN stocks s ON p.id = s.produit_id
            WHERE 1=1
        '''
        params = []
        
        if societe_filter and societe_filter in SOCIETES:
            query += ' AND p.societe = ?'
            params.append(societe_filter)
        
        query += ' ORDER BY p.societe, p.nom'
        
        cursor.execute(query, params)
        produits = cursor.fetchall()
        conn.close()
        
        result = []
        date_aujourdhui = datetime.now()
        
        for p in produits:
            produit_dict = dict(p)
            
            # Calcul jours restants
            if produit_dict.get('date_peremption'):
                try:
                    # Gérer les formats de date MySQL vs SQLite
                    if isinstance(produit_dict['date_peremption'], str):
                        dp = datetime.strptime(produit_dict['date_peremption'], '%Y-%m-%d')
                    else:
                        dp = datetime.combine(produit_dict['date_peremption'], datetime.min.time())
                        
                    delta = dp - date_aujourdhui
                    produit_dict['jours_restants'] = delta.days
                except:
                    produit_dict['jours_restants'] = None
            else:
                produit_dict['jours_restants'] = None
                
            if not with_stock:
                produit_dict.pop('stock_actuel', None)
            result.append(produit_dict)
        
        return jsonify({'success': True, 'produits': result})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@produits_bp.route('/<int:produit_id>', methods=['GET'])
def get_produit(produit_id):
    """Retourne un produit spécifique"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT p.*, s.quantite as stock_actuel
            FROM produits p
            LEFT JOIN stocks s ON p.id = s.produit_id
            WHERE p.id = ?
        ''', (produit_id,))
        
        produit = cursor.fetchone()
        conn.close()
        
        if produit:
            return jsonify({'success': True, 'produit': dict(produit)})
        else:
            return jsonify({'success': False, 'message': 'Produit non trouvé'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@produits_bp.route('/', methods=['POST'])
def create_produit():
    """Crée un nouveau produit"""
    try:
        data = request.get_json()
        
        # Validation
        required = ['nom', 'societe', 'prix_achat', 'prix_vente']
        for field in required:
            if field not in data:
                return jsonify({'success': False, 'message': f'Champ manquant: {field}'}), 400
        
        if data['societe'] not in SOCIETES:
            return jsonify({'success': False, 'message': 'Société invalide'}), 400
        
        seuil = data.get('seuil_alerte', 10)
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Insertion produit
        cursor.execute('''
            INSERT INTO produits (nom, societe, prix_achat, prix_vente, seuil_alerte, date_peremption)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (data['nom'], data['societe'], data['prix_achat'], data['prix_vente'], seuil, data.get('date_peremption')))
        
        produit_id = cursor.lastrowid
        
        # Création entrée stock avec quantité initiale
        stock_init = data.get('stock_initial', 0)
        cursor.execute('''
            INSERT INTO stocks (produit_id, quantite)
            VALUES (?, ?)
        ''', (produit_id, stock_init))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Produit créé avec succès',
            'produit_id': produit_id
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@produits_bp.route('/<int:produit_id>', methods=['PUT'])
def update_produit(produit_id):
    """Met à jour un produit existant"""
    try:
        data = request.get_json()
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Vérifier que le produit existe
        cursor.execute('SELECT id FROM produits WHERE id = ?', (produit_id,))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'Produit non trouvé'}), 404
        
        # Construction dynamique de la requête UPDATE
        updates = []
        params = []
        
        fields = ['nom', 'societe', 'prix_achat', 'prix_vente', 'seuil_alerte', 'date_peremption']
        for field in fields:
            if field in data:
                val = data[field]
                if field == 'date_peremption' and not val:
                    val = None
                updates.append(f"{field} = ?")
                params.append(val)
        
        if updates:
            date_actuelle = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            params.append(produit_id)
            cursor.execute(f'''
                UPDATE produits 
                SET {', '.join(updates)}, updated_at = ?
                WHERE id = ?
            ''', (*params[:-1], date_actuelle, params[-1]))
            
            conn.commit()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Produit mis à jour avec succès'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@produits_bp.route('/<int:produit_id>', methods=['DELETE'])
def delete_produit(produit_id):
    """Supprime un produit (soft delete ou réel)"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Vérifier si le produit a des ventes
        cursor.execute('SELECT COUNT(*) as count FROM ventes WHERE produit_id = ?', (produit_id,))
        ventes_count = cursor.fetchone()['count']
        
        if ventes_count > 0:
            # Soft delete : on pourrait ajouter un champ 'actif' mais pour l'instant on refuse
            return jsonify({
                'success': False, 
                'message': 'Impossible de supprimer : le produit a des ventes associées'
            }), 400
        
        # Supprimer d'abord l'entrée stock
        cursor.execute('DELETE FROM stocks WHERE produit_id = ?', (produit_id,))
        
        # Puis le produit
        cursor.execute('DELETE FROM produits WHERE id = ?', (produit_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Produit supprimé avec succès'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@produits_bp.route('/societes', methods=['GET'])
def get_societes():
    """Retourne la liste des sociétés"""
    return jsonify({'success': True, 'societes': SOCIETES})