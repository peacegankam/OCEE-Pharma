# app.py (version corrigée)
from flask import Flask, render_template, jsonify, request, send_file, session, redirect, url_for
import json
import os
from datetime import datetime, timedelta
from functools import wraps

# Import des modules de configuration
from config import NOM_BAR, DEVISE, ADMIN_PIN

# Import des routes (blueprints)
from routes.produits import produits_bp
from routes.ventes import ventes_bp
from routes.stocks import stocks_bp
from routes.appro import appro_bp
from routes.ml import ml_bp
from routes.dashboard import dashboard_bp
from routes.rapports import rapports_bp

from routes.admin import admin_bp

# Création de l'application Flask
app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')

app.config['SECRET_KEY'] = 'pharma-moderne-secret-key-2024'
app.config['NOM_BAR'] = NOM_BAR
app.config['DEVISE'] = DEVISE

# Enregistrement des blueprints (avec ou sans préfixe)
app.register_blueprint(produits_bp, url_prefix='/api/produits')
app.register_blueprint(ventes_bp, url_prefix='/api/ventes')
app.register_blueprint(stocks_bp, url_prefix='/api/stocks')
app.register_blueprint(appro_bp, url_prefix='/api/appro')
app.register_blueprint(ml_bp, url_prefix='/api/ml')
app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
app.register_blueprint(rapports_bp, url_prefix='/api/rapports')

app.register_blueprint(admin_bp, url_prefix='/admin')

# ========== MIDDLEWARE D'AUTHENTIFICATION ==========

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ========== ROUTES AUTHENTIFICATION ==========

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Page de sélection de profil (Point de Vente) / Traitement login"""
    import database
    
    conn = database.get_db()
    cursor = conn.cursor()
    
    # Récupérer les paramètres de base
    cursor.execute("SELECT valeur FROM parametres WHERE clef='NOM_BAR'")
    row_nom = cursor.fetchone()
    nom_actuel = row_nom['valeur'] if row_nom else NOM_BAR
    
    cursor.execute("SELECT * FROM utilisateurs ORDER BY role ASC, nom ASC")
    utilisateurs = [dict(row) for row in cursor.fetchall()]
    
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        pin = request.form.get('pin', '')
        
        cursor.execute("SELECT * FROM utilisateurs WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            # Vérifier le PIN si l'utilisateur en a un
            if user['code_pin'] and user['code_pin'] != pin:
                return render_template('login.html', error="Code PIN incorrect", nom_bar=nom_actuel, utilisateurs=utilisateurs)
                
            session['user_id'] = user['id']
            session['nom'] = user['nom']
            session['role'] = user['role']
            return redirect(url_for('index'))
            
    conn.close()
    return render_template('login.html', nom_bar=nom_actuel, utilisateurs=utilisateurs)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ========== ROUTES PAGES ==========

@app.route('/')
@login_required
def index():
    """Page d'accueil / Dashboard principal"""
    return render_template('index.html', 
                         nom_bar=NOM_BAR,
                         devise=DEVISE,
                         annee=datetime.now().year)

@app.route('/produits')
@login_required
def produits_page():
    """Page de gestion des produits"""
    return render_template('produits.html',
                         nom_bar=NOM_BAR,
                         devise=DEVISE)

@app.route('/caisse')
@login_required
def caisse_page():
    """Page de caisse / enregistrement des ventes"""
    return render_template('caisse.html',
                         nom_bar=NOM_BAR,
                         devise=DEVISE)

@app.route('/stocks')
@login_required
def stocks_page():
    """Page de gestion des stocks"""
    return render_template('stocks.html',
                         nom_bar=NOM_BAR,
                         devise=DEVISE)

@app.route('/appro')
@login_required
def appro_page():
    """Page d'approvisionnement"""
    return render_template('appro.html',
                         nom_bar=NOM_BAR,
                         devise=DEVISE)

@app.route('/tendances')
@login_required
def tendances_page():
    """Page des tendances et ML"""
    return render_template('tendances.html',
                         nom_bar=NOM_BAR,
                         devise=DEVISE)

@app.route('/bilan')
@login_required
def bilan_page():
    """Page de bilan financier"""
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
    return render_template('bilan.html',
                         nom_bar=NOM_BAR,
                         devise=DEVISE)

@app.route('/rapport')
@login_required
def rapport_page():
    """Page de rapport journalier"""
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
    return render_template('rapport.html',
                         nom_bar=NOM_BAR,
                         devise=DEVISE)

# ========== ROUTE DE TEST API ==========

@app.route('/api/test')
def test_api():
    """Route simple pour tester que l'API fonctionne"""
    return jsonify({
        'success': True,
        'message': 'API fonctionne correctement',
        'time': datetime.now().isoformat()
    })

# ========== MIDDLEWARE ==========

@app.after_request
def add_header(response):
    """Ajoute des headers pour éviter le cache en développement"""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# ========== GESTION DES ERREURS ==========

@app.errorhandler(404)
def page_not_found(e):
    return jsonify({'success': False, 'message': 'Page non trouvée'}), 404

@app.errorhandler(500)
def internal_server_error(e):
    return jsonify({'success': False, 'message': 'Erreur interne du serveur'}), 500

# ========== LANCEMENT ==========

if __name__ == '__main__':
    print(f"""
     {NOM_BAR} - Dashboard de Gestion
    ===================================
    Interface: http://localhost:5000
    Test API:  http://localhost:5000/api/test
    Base: data/pharma.sqlite
    ===================================
    """)
    app.run(debug=True, host='0.0.0.0', port=5000)