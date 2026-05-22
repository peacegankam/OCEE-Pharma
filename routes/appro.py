# routes/appro.py - Routes pour les approvisionnements
from flask import Blueprint, jsonify, request, session
from database import get_db
from datetime import datetime, timedelta

appro_bp = Blueprint('appro', __name__)


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

@appro_bp.route('/', methods=['POST'])
def enregistrer_appro():
    """Enregistre un nouvel approvisionnement"""
    try:
        data = request.get_json()
        
        required = ['produit_id', 'prix_carton', 'quantite_cartons', 'produits_par_carton', 'date_peremption']
        for field in required:
            if field not in data:
                return jsonify({'success': False, 'message': f'Champ manquant: {field}'}), 400
        
        produit_id = data['produit_id']
        prix_carton = data['prix_carton']
        quantite_cartons = data['quantite_cartons']
        produits_par_carton = data['produits_par_carton']
        date_perempt = data['date_peremption']
        date_reception = data.get('date_reception', '').strip()
        fournisseur = data.get('fournisseur', '').strip()

        # Si fournisseur n'est pas fourni (champ retiré côté UI), on l'ignore côté API.
        # (champ stocké éventuellement dans lots_stock)
        if not fournisseur:
            fournisseur = ''

        note = data.get('note', '')


        if quantite_cartons <= 0 or produits_par_carton <= 0 or prix_carton <= 0:
            return jsonify({'success': False, 'message': 'Quantités et prix doivent être strictement positifs'}), 400

        quantite = int(quantite_cartons * produits_par_carton)
        prix_achat = int(round(prix_carton / produits_par_carton))
        cout_total = int(round(prix_carton * quantite_cartons))
        pvu = int(round(prix_achat * 1.5))
        ref_lot = data.get('reference_lot', f'LOT-{datetime.now().strftime("%y%m%d%H%M")}')

        conn = get_db()
        cursor = conn.cursor()
        
        # Vérifier que le produit existe
        cursor.execute('SELECT * FROM produits WHERE id = ?', (produit_id,))
        produit = cursor.fetchone()
        
        if not produit:
            conn.close()
            return jsonify({'success': False, 'message': 'Produit non trouvé'}), 404

        # gérer le fournisseur existant ou créer un nouveau si nécessaire
        if fournisseur:
            cursor.execute('SELECT id FROM fournisseurs WHERE LOWER(nom) = LOWER(?)', (fournisseur,))
            if not cursor.fetchone():
                cursor.execute('INSERT INTO fournisseurs (nom) VALUES (?)', (fournisseur,))

        # Récupérer le stock actuel + seuil
        cursor.execute('SELECT quantite FROM stocks WHERE produit_id = ?', (produit_id,))
        stock_actuel = cursor.fetchone()

        ancien_stock = stock_actuel['quantite'] if stock_actuel else 0
        seuil_alerte = produit['seuil_alerte'] if 'seuil_alerte' in produit.keys() else None
        if date_reception:
            try:
                date_actuelle = datetime.strptime(date_reception, '%Y-%m-%d').strftime('%Y-%m-%d') + ' ' + datetime.now().strftime('%H:%M:%S')
            except Exception:
                date_actuelle = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        else:
            date_actuelle = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        stock_initial_details = get_lots_details_str(cursor, produit_id)

        cursor.execute('''
            INSERT INTO approvisionnements 
            (produit_id, quantite, prix_achat_unitaire, note, date_appro)
            VALUES (?, ?, ?, ?, ?)
        ''', (produit_id, quantite, prix_achat, note or f'Livraison {quantite_cartons} cartons', date_actuelle))
        
        cursor.execute('''
            INSERT INTO lots_stock 
            (produit_id, quantite_initiale, quantite_actuelle, prix_achat_unitaire, prix_vente_unitaire, 
             date_peremption, reference_lot, date_reception, quantite_cartons, produits_par_carton, prix_carton, fournisseur)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (produit_id, quantite, quantite, prix_achat, pvu, 
              date_perempt, ref_lot, date_actuelle, 
              quantite_cartons, produits_par_carton, prix_carton, fournisseur or None))

        cursor.execute('''
            UPDATE produits 
            SET prix_achat = ?, prix_vente = ?
            WHERE id = ?
        ''', (prix_achat, pvu, produit_id))

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
        
        stock_final_details = get_lots_details_str(cursor, produit_id)

        utilisateur_id = session.get('user_id')
        cursor.execute('''
            INSERT INTO historique_stock 
            (produit_id, quantite_avant, quantite_apres, type, raison, date_mouvement, utilisateur_id, 
             stock_initial_details, stock_final_details, perte_financiere)
            VALUES (?, ?, ?, 'appro', ?, ?, ?, ?, ?, 0)
        ''', (produit_id, ancien_stock, ancien_stock + quantite, note or 'Approvisionnement', 
              date_actuelle, utilisateur_id, stock_initial_details, stock_final_details))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Approvisionnement et lot enregistrés avec succès',
            'nouveau_stock': ancien_stock + quantite,
            'prix_achat_unitaire': prix_achat,
            'prix_vente_unitaire': pvu,
            'cout_total': cout_total
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@appro_bp.route('/fournisseurs', methods=['GET'])
def get_fournisseurs():
    """Retourne la liste des fournisseurs"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT id, nom FROM fournisseurs')
        rows = cursor.fetchall()
        conn.close()

        # Normaliser quelques variantes de noms et ordonner
        preferred = ['Ubipharm', 'Laborex', 'PharmaCentrale']
        norm_map = {
            'ubipharma': 'Ubipharm',
            'ubipharm': 'Ubipharm',
            'pharmacentral': 'PharmaCentrale',
            'pharmacentrale': 'PharmaCentrale'
        }

        fournisseurs = []
        for r in rows:
            nom = r['nom'] or ''
            key = nom.replace(' ', '').lower()
            if key in norm_map:
                nom_norm = norm_map[key]
            else:
                nom_norm = nom
            fournisseurs.append({'id': r['id'], 'nom': nom_norm})

        # Mettre en tête les préférés dans l'ordre donné
        pref_list = [f for name in preferred for f in fournisseurs if f['nom'] == name]
        others = [f for f in fournisseurs if f['nom'] not in preferred]
        ordered = pref_list + sorted(others, key=lambda x: (x['nom'] or '').lower())

        return jsonify({'success': True, 'fournisseurs': ordered})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@appro_bp.route('/fournisseurs', methods=['POST'])
def creer_fournisseur():
    """Ajoute un nouveau fournisseur"""
    try:
        data = request.get_json() or {}
        nom = (data.get('nom') or '').strip()
        if not nom:
            return jsonify({'success': False, 'message': 'Nom fournisseur requis'}), 400

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM fournisseurs WHERE LOWER(nom) = LOWER(?)', (nom,))
        exists = cursor.fetchone()
        if exists:
            conn.close()
            return jsonify({'success': True, 'message': 'Fournisseur déjà existant', 'id': exists['id']})

        cursor.execute('INSERT INTO fournisseurs (nom) VALUES (?)', (nom,))
        fournisseur_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'message': 'Fournisseur créé', 'id': fournisseur_id})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@appro_bp.route('/bon-commande', methods=['POST'])
def enregistrer_bon_commande():
    """Enregistre un bon de commande."""
    try:
        if session.get('role') != 'admin':
            return jsonify({'success': False, 'message': 'Accès refusé : seul le gérant peut enregistrer un bon de commande.'}), 403

        data = request.get_json() or {}
        produit_nom = (data.get('produit_nom') or '').strip()
        societe = (data.get('societe') or '').strip()
        quantite_cartons = data.get('quantite_cartons')
        fournisseur = (data.get('fournisseur') or '').strip()
        date_commande = data.get('date_commande')

        if not produit_nom:
            return jsonify({'success': False, 'message': 'Nom du médicament requis.'}), 400
        if not societe:
            return jsonify({'success': False, 'message': 'Famille/société du produit requise.'}), 400
        if not quantite_cartons or int(quantite_cartons) <= 0:
            return jsonify({'success': False, 'message': 'Nombre de cartons doit être strictement positif.'}), 400
        if not fournisseur:
            return jsonify({'success': False, 'message': 'Fournisseur requis.'}), 400
        if not date_commande:
            return jsonify({'success': False, 'message': 'Date de commande requise.'}), 400

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO bons_commande
            (produit_nom, societe, quantite_cartons, fournisseur, date_commande, utilisateur_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (produit_nom, societe, int(quantite_cartons), fournisseur, date_commande, session.get('user_id')))

        conn.commit()
        conn.close()

        return jsonify({'success': True, 'message': 'Bon de commande enregistré avec succès.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

        if total_lignes == 0:
            conn.close()
            return jsonify({'success': False, 'message': 'Aucune ligne valide dans le bon de commande'}), 400

        conn.commit()
        conn.close()

        return jsonify({'success': True, 'message': 'Bon de commande enregistré et stock mis à jour', 'lignes': total_lignes})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@appro_bp.route('/historique', methods=['GET'])
def get_historique_appro():
    """Retourne l'historique des approvisionnements"""
    try:
        periode = request.args.get('periode', 'semaine')
        debut = request.args.get('debut')
        fin = request.args.get('fin')
        fournisseur = request.args.get('fournisseur', '').strip()
        produit_recherche = request.args.get('produit', '').strip().lower()

        conn = get_db()
        cursor = conn.cursor()

        query = '''
            SELECT 
                l.id,
                l.date_reception as date_appro,
                p.nom as produit,
                p.societe,
                l.quantite_actuelle as quantite,
                l.prix_achat_unitaire,
                l.prix_vente_unitaire,
                l.quantite_cartons,
                l.produits_par_carton,
                l.prix_carton,
                l.fournisseur,
                l.date_peremption,
                l.reference_lot
            FROM lots_stock l
            JOIN produits p ON l.produit_id = p.id
            WHERE 1=1
        '''
        params = []

        today = datetime.now().date()
        if not debut and not fin:
            if periode == 'jour':
                debut = fin = today.isoformat()
            elif periode == 'semaine':
                debut = (today - timedelta(days=6)).isoformat()
                fin = today.isoformat()
            elif periode == 'mois':
                debut = today.replace(day=1).isoformat()
                fin = today.isoformat()

        if debut:
            query += ' AND DATE(l.date_reception) >= ?'
            params.append(debut)
        if fin:
            query += ' AND DATE(l.date_reception) <= ?'
            params.append(fin)
        if fournisseur:
            query += ' AND LOWER(l.fournisseur) LIKE ?'
            params.append(f'%{fournisseur.lower()}%')
        if produit_recherche:
            query += ' AND LOWER(p.nom) LIKE ?'
            params.append(f'%{produit_recherche}%')

        query += ' ORDER BY l.date_reception DESC LIMIT 100'

        cursor.execute(query, params)
        lots = cursor.fetchall()
        conn.close()

        return jsonify({
            'success': True,
            'approvisionnements': [dict(l) for l in lots]
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
    """Retourne les statistiques des approvisionnements selon une période"""
    try:
        periode = request.args.get('periode', 'jour')
        conn = get_db()
        cursor = conn.cursor()
        
        today = datetime.now().date()
        debut = today
        fin = today

        if periode == 'semaine':
            debut = today - timedelta(days=6)
        elif periode == 'mois':
            debut = today.replace(day=1)
        else:
            periode = 'jour'

        cursor.execute('''
            SELECT 
                COUNT(*) as nb_appro,
                COALESCE(SUM(quantite * prix_achat_unitaire), 0) as total_depenses,
                COALESCE(SUM(quantite), 0) as total_articles
            FROM approvisionnements
            WHERE DATE(date_appro) BETWEEN ? AND ?
        ''', (debut.isoformat(), fin.isoformat()))
        
        stats = cursor.fetchone()
        
        date_limite = today - timedelta(days=7)
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
            'periode': periode,
            'nb_appro': stats['nb_appro'],
            'total_depenses': stats['total_depenses'],
            'total_articles': stats['total_articles'],
            'top_produits': [dict(t) for t in top]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500