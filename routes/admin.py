from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from database import get_db

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# GESTION DES EMPLOYÉS
# ==========================================

@admin_bp.route('/employes', methods=['GET'])
@admin_required
def employes_page():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.*, 
               COUNT(v.id) as nb_ventes,
               COALESCE(SUM(v.quantite * v.prix_unitaire), 0) as total_vendu
        FROM utilisateurs u
        LEFT JOIN ventes v ON u.id = v.vendeur_id
        GROUP BY u.id
        ORDER BY u.role ASC, u.nom ASC
    ''')
    utilisateurs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return render_template('employes.html', utilisateurs=utilisateurs)

@admin_bp.route('/api/employes', methods=['POST'])
@admin_required
def add_employe():
    data = request.get_json()
    nom = data.get('nom')
    role = data.get('role', 'employe')
    code_pin = data.get('code_pin', '')
    
    if not nom:
        return jsonify({'success': False, 'message': 'Le nom est requis'})
        
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO utilisateurs (nom, role, code_pin) VALUES (?, ?, ?)", 
                      (nom, role, code_pin))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@admin_bp.route('/api/employes/<int:id>', methods=['DELETE'])
@admin_required
def delete_employe(id):
    if id == session.get('user_id'):
        return jsonify({'success': False, 'message': 'Vous ne pouvez pas supprimer votre propre compte'})
        
    try:
        conn = get_db()
        cursor = conn.cursor()
        print(f"Tentative de suppression de l'utilisateur ID {id}")
        cursor.execute("DELETE FROM utilisateurs WHERE id = ?", (id,))
        conn.commit()
        conn.close()
        print(f"Utilisateur {id} supprimé avec succès")
        return jsonify({'success': True})
    except Exception as e:
        print(f"Erreur lors de la suppression de l'utilisateur {id}: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

# ==========================================
# GESTION DES PARAMÈTRES
# ==========================================

@admin_bp.route('/parametres', methods=['GET'])
@admin_required
def parametres_page():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM parametres")
    params = {row['clef']: row['valeur'] for row in cursor.fetchall()}
    conn.close()
    
    return render_template('parametres.html', params=params)

@admin_bp.route('/api/parametres', methods=['POST'])
@admin_required
def save_parametres():
    data = request.get_json()
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        for clef, valeur in data.items():
            # Upsert
            cursor.execute('''
                INSERT INTO parametres (clef, valeur) 
                VALUES (?, ?) 
                ON CONFLICT(clef) DO UPDATE SET valeur=?
            ''', (clef, str(valeur), str(valeur)))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
