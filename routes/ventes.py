# routes/ventes.py - Routes pour l'enregistrement des ventes
from flask import Blueprint, jsonify, request, session
from database import get_db
from datetime import datetime, timedelta

ventes_bp = Blueprint('ventes', __name__)

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
        notes_vendeur = []
        date_actuelle = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        today_str = datetime.now().date().isoformat()
        
        for vente in ventes:
            produit_id = vente['produit_id']
            quantite_a_vendre = vente['quantite']
            prix_final = vente.get('prix_unitaire')
            
            # 1. Vérifier les lots disponibles (FIFO : triés par date de réception)
            cursor.execute('''
                SELECT id, quantite_actuelle, prix_achat_unitaire, date_peremption, reference_lot
                FROM lots_stock
                WHERE produit_id = ? AND quantite_actuelle > 0
                ORDER BY date_reception ASC
            ''', (produit_id,))
            lots = cursor.fetchall()
            
            # 2. Filtrer les lots non périmés
            lots_valides = []
            lots_perimes_ignores = 0
            for l in lots:
                if l['date_peremption'] and str(l['date_peremption']) < today_str:
                    lots_perimes_ignores += l['quantite_actuelle']
                    continue
                lots_valides.append(l)
            
            stock_valide = sum(l['quantite_actuelle'] for l in lots_valides)
            
            if stock_valide < quantite_a_vendre:
                conn.rollback()
                msg = f"Stock insuffisant pour le produit {produit_id}."
                if lots_perimes_ignores > 0:
                    msg += f" ({lots_perimes_ignores} unités sont périmées et ont été bloquées)."
                return jsonify({'success': False, 'message': msg}), 400

            if lots_perimes_ignores > 0:
                notes_vendeur.append(f"Info: {lots_perimes_ignores} unités périmées ignorées pour le produit {produit_id}")

            # 3. Récupérer le prix de vente par défaut si non fourni
            if not prix_final:
                cursor.execute("SELECT prix_vente FROM produits WHERE id = ?", (produit_id,))
                p_row = cursor.fetchone()
                prix_final = p_row['prix_vente'] if p_row else 0

            # Récupérer le stock global avant la vente
            cursor.execute('SELECT quantite FROM stocks WHERE produit_id = ?', (produit_id,))
            s_row = cursor.fetchone()
            s_avant = s_row['quantite'] if s_row else 0
            s_apres = s_avant - quantite_a_vendre

            # Capturer le stock initial sous forme détaillée
            stock_initial_details = get_lots_details_str(cursor, produit_id)

            # 4. Enregistrer la vente principale
            vendeur_id = session.get('user_id')
            cursor.execute('''
                INSERT INTO ventes (produit_id, quantite, prix_unitaire, vendeur_id, date_vente)
                VALUES (?, ?, ?, ?, ?)
            ''', (produit_id, quantite_a_vendre, prix_final, vendeur_id, date_actuelle))
            vente_id = cursor.lastrowid
            
            # 5. Consommer les lots (FIFO)
            restant = quantite_a_vendre
            benefice_produit = 0
            for lot in lots_valides:
                if restant <= 0: break
                
                prendre = min(restant, lot['quantite_actuelle'])
                restant -= prendre
                benefice_produit += prendre * (prix_final - lot['prix_achat_unitaire'])
                
                # Mettre à jour le lot
                cursor.execute('''
                    UPDATE lots_stock 
                    SET quantite_actuelle = quantite_actuelle - ? 
                    WHERE id = ?
                ''', (prendre, lot['id']))
                
                # Enregistrer le détail du lot vendu
                cursor.execute('''
                    INSERT INTO vente_lots (vente_id, lot_id, quantite, prix_achat_unitaire)
                    VALUES (?, ?, ?, ?)
                ''', (vente_id, lot['id'], prendre, lot['prix_achat_unitaire']))

            # 6. Mettre à jour le stock global (pour compatibilité)
            cursor.execute('''
                UPDATE stocks SET quantite = quantite - ?, derniere_maj = ? WHERE produit_id = ?
            ''', (quantite_a_vendre, date_actuelle, produit_id))
            
            # Capturer le stock final sous forme détaillée
            stock_final_details = get_lots_details_str(cursor, produit_id)

            # 7. Historique de mouvement
            cursor.execute('''
                INSERT INTO historique_stock 
                (produit_id, quantite_avant, quantite_apres, type, raison, date_mouvement, utilisateur_id,
                 stock_initial_details, stock_final_details, perte_financiere)
                VALUES (?, ?, ?, 'vente', 'Vente FIFO', ?, ?, ?, ?, 0)
            ''', (produit_id, s_avant, s_apres, date_actuelle, vendeur_id, stock_initial_details, stock_final_details))

            total_vente += quantite_a_vendre * prix_final
            total_benefice += benefice_produit
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'{len(ventes)} vente(s) enregistrée(s)',
            'total': total_vente,
            'benefice': total_benefice,
            'notes': notes_vendeur,
            'date_vente': date_actuelle
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

        cursor.execute('''
            SELECT v.id, v.produit_id, v.quantite, v.prix_unitaire, v.date_vente,
                   p.nom, p.societe, p.prix_achat
            FROM ventes v
            JOIN produits p ON v.produit_id = p.id
            WHERE DATE(v.date_vente) = ?
            ORDER BY v.date_vente DESC
        ''', (today.isoformat(),))
        rows = cursor.fetchall()

        ventes = []
        total = 0
        benefice = 0
        for r in rows:
            d = dict(r)
            d['heure'] = str(d['date_vente'])[11:16]
            d['total'] = d['quantite'] * d['prix_unitaire']
            total += d['total']
            benefice += d['quantite'] * (d['prix_unitaire'] - d['prix_achat'])
            ventes.append(d)

        conn.close()
        return jsonify({
            'success': True,
            'nb_ventes': len(ventes),
            'total': total,
            'benefice': benefice,
            'ventes': ventes
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@ventes_bp.route('/filtres', methods=['GET'])
def get_ventes_filtres():
    """Retourne les ventes avec filtres avancés"""
    try:
        periode  = request.args.get('periode', 'jour')   # jour|semaine|mois|tout
        produit  = request.args.get('produit', '')        # recherche texte
        qte_op   = request.args.get('qte_op', '')         # >|<|=
        qte_val  = request.args.get('qte_val', '', type=str)

        conn = get_db()
        cursor = conn.cursor()

        # Condition de période
        today = datetime.now().date()
        if periode == 'jour':
            date_debut = today.isoformat()
            date_fin   = today.isoformat()
        elif periode == 'semaine':
            date_debut = (today - timedelta(days=6)).isoformat()
            date_fin   = today.isoformat()
        elif periode == 'mois':
            date_debut = today.replace(day=1).isoformat()
            date_fin   = today.isoformat()
        else:  # tout
            date_debut = '2000-01-01'
            date_fin   = today.isoformat()

        # Construction de la requête SQL
        conditions = ['DATE(v.date_vente) BETWEEN ? AND ?']
        params = [date_debut, date_fin]

        if produit:
            conditions.append('LOWER(p.nom) LIKE ?')
            params.append(f'%{produit.lower()}%')

        if qte_op in ('>', '<', '=') and qte_val.isdigit():
            conditions.append(f'v.quantite {qte_op} ?')
            params.append(int(qte_val))

        where_clause = ' AND '.join(conditions)

        cursor.execute(f'''
            SELECT v.id, v.quantite, v.prix_unitaire, v.date_vente,
                   p.nom, p.societe, p.prix_achat
            FROM ventes v
            JOIN produits p ON v.produit_id = p.id
            WHERE {where_clause}
            ORDER BY v.date_vente DESC
        ''', params)

        rows = cursor.fetchall()
        ventes = []
        total = 0
        for r in rows:
            d = dict(r)
            d['heure'] = str(d['date_vente'])[11:16]
            d['date'] = str(d['date_vente'])[:10]
            d['total'] = d['quantite'] * d['prix_unitaire']
            total += d['total']
            ventes.append(d)

        conn.close()
        return jsonify({'success': True, 'ventes': ventes, 'total': total, 'nb': len(ventes)})
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