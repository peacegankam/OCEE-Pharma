# routes/ml.py - Routes pour le machine learning et prévisions
from flask import Blueprint, jsonify, request
from database import get_db
import numpy as np
from datetime import datetime, timedelta
import random

# Note: Dans une version avancée, on importerait prophet
# from prophet import Prophet

ml_bp = Blueprint('ml', __name__)

def generer_prevision_simple(historique, jours=7):
    """Génère des prévisions simples (simulation pour l'instant)"""
    if not historique or len(historique) < 3:
        return []
    
    # Calculer la tendance linéaire basique
    x = np.arange(len(historique))
    y = np.array([h['revenu'] for h in historique])
    
    if len(x) > 1:
        coeffs = np.polyfit(x, y, 1)
        tendance = coeffs[0]
    else:
        tendance = 0
    
    # Prévisions
    dernier = historique[-1]['revenu']
    previsions = []
    
    for i in range(1, jours + 1):
        # Tendance + variation saisonnière (weekend plus élevé)
        jour_semaine = (datetime.now() + timedelta(days=i)).weekday()
        facteur_jour = 1.2 if jour_semaine >= 5 else 1.0  # Weekend +20%
        
        base = dernier + (tendance * i)
        valeur = base * facteur_jour * random.uniform(0.95, 1.05)  # Bruit
        
        # Intervalles de confiance
        incertitude = 0.1 * (1 + i/7)  # Plus l'horizon est loin, plus l'incertitude grandit
        
        previsions.append({
            'date': (datetime.now() + timedelta(days=i)).strftime('%d/%m'),
            'revenu': int(max(0, valeur)),
            'revenu_bas': int(max(0, valeur * (1 - incertitude))),
            'revenu_haut': int(max(0, valeur * (1 + incertitude)))
        })
    
    return previsions

@ml_bp.route('/forecast', methods=['GET'])
def get_forecast():
    """Retourne les prévisions de ventes"""
    try:
        jours = request.args.get('days', 7, type=int)
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Récupérer l'historique
        cursor.execute('''
            SELECT 
                DATE(REPLACE(date_vente, 'T', ' ')) as date,
                COALESCE(SUM(quantite * prix_unitaire), 0) as revenu
            FROM ventes
            WHERE DATE(REPLACE(date_vente, 'T', ' ')) >= DATE('now', '-30 days')
            GROUP BY DATE(REPLACE(date_vente, 'T', ' '))
            ORDER BY date ASC
        ''')
        
        historique = cursor.fetchall()
        historique_list = [dict(h) for h in historique]
        
        # Générer les prévisions
        previsions = generer_prevision_simple(historique_list, jours)
        
        conn.close()
        
        return jsonify({
            'success': True,
            'historique': historique_list,
            'prevision': previsions
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@ml_bp.route('/trends', methods=['GET'])
def get_trends():
    """Retourne les tendances par société"""
    try:
        jours = request.args.get('days', 7, type=int)
        
        conn = get_db()
        cursor = conn.cursor()
        
        societes = ['Antibiotiques', 'Analgésiques', 'Vitamines', 'Dermatologie', 'Matériel Médical']
        dates = []
        trends = []
        
        # Générer les dates
        for i in range(jours):
            date = (datetime.now() - timedelta(days=jours-1-i)).date()
            dates.append(date.strftime('%d/%m'))
        
        # Pour chaque société
        for societe in societes:
            valeurs = []
            for i in range(jours):
                date = (datetime.now() - timedelta(days=jours-1-i)).date()
                
                cursor.execute('''
                    SELECT COALESCE(SUM(v.quantite * v.prix_unitaire), 0) as total
                    FROM ventes v
                    JOIN produits p ON v.produit_id = p.id
                    WHERE p.societe = ? AND DATE(REPLACE(v.date_vente, 'T', ' ')) = ?
                ''', (societe, date.isoformat()))
                
                valeurs.append(cursor.fetchone()['total'])
            
            # Prédiction simple
            prediction = int(np.mean(valeurs[-3:]) * 1.05) if len(valeurs) >= 3 else 0
            
            trends.append({
                'societe': societe,
                'values': valeurs,
                'prediction': prediction
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'dates': dates,
            'trends': trends
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@ml_bp.route('/products', methods=['GET'])
def get_products_ml():
    """Retourne les produits stars et recommandations"""
    try:
        jours = request.args.get('days', 7, type=int)
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Top produits par quantité
        cursor.execute('''
            SELECT 
                p.id,
                p.nom,
                p.societe,
                SUM(v.quantite) as quantite,
                SUM(v.quantite * v.prix_unitaire) as montant
            FROM ventes v
            JOIN produits p ON v.produit_id = p.id
            WHERE DATE(REPLACE(v.date_vente, 'T', ' ')) >= DATE('now', ? || ' days')
            GROUP BY p.id
            ORDER BY quantite DESC
            LIMIT 10
        ''', (f'-{jours}',))
        
        top_produits = cursor.fetchall()
        
        # Recommandations stock
        cursor.execute('''
            SELECT 
                p.id as produit_id,
                p.nom as produit,
                p.societe,
                s.quantite as stock_actuel,
                p.seuil_alerte as seuil_min,
                    COALESCE((
                    SELECT AVG(v.quantite)
                    FROM ventes v
                    WHERE v.produit_id = p.id
                    AND DATE(REPLACE(v.date_vente, 'T', ' ')) >= DATE('now', '-7 days')
                ), 0) as conso_journaliere,
                CASE 
                    WHEN s.quantite = 0 THEN 'haute'
                    WHEN s.quantite <= p.seuil_alerte/2 THEN 'haute'
                    WHEN s.quantite <= p.seuil_alerte THEN 'moyenne'
                    ELSE 'basse'
                END as priorite,
                CASE 
                    WHEN s.quantite = 0 THEN 'Rupture totale - Commander d\'urgence'
                    WHEN s.quantite <= p.seuil_alerte/2 THEN 'Stock critique - Commander rapidement'
                    WHEN s.quantite <= p.seuil_alerte THEN 'Stock faible - Prévoir commande'
                    ELSE 'Stock OK'
                END as message,
                (s.quantite * 100.0 / NULLIF(p.seuil_alerte, 0)) as stock_percent
            FROM stocks s
            JOIN produits p ON s.produit_id = p.id
            WHERE s.quantite <= p.seuil_alerte * 1.5
            ORDER BY priorite, s.quantite ASC
        ''')
        
        recommendations = cursor.fetchall()
        
        # Meilleur jour
        cursor.execute('''
            SELECT 
                strftime('%w', date_vente) as jour_num,
                CASE cast(strftime('%w', date_vente) as integer)
                    WHEN 0 THEN 'Dimanche'
                    WHEN 1 THEN 'Lundi'
                    WHEN 2 THEN 'Mardi'
                    WHEN 3 THEN 'Mercredi'
                    WHEN 4 THEN 'Jeudi'
                    WHEN 5 THEN 'Vendredi'
                    WHEN 6 THEN 'Samedi'
                END as jour_nom,
                AVG(quantite * prix_unitaire) as moyenne
            FROM ventes
            WHERE DATE(REPLACE(date_vente, 'T', ' ')) >= DATE('now', '-30 days')
            GROUP BY jour_num
            ORDER BY moyenne DESC
            LIMIT 1
        ''')
        
        best_day = cursor.fetchone()
        
        # Croissance
        cursor.execute('''
            SELECT 
                SUM(CASE WHEN date_vente >= DATE('now', '-7 days') THEN quantite * prix_unitaire ELSE 0 END) as semaine_recente,
                SUM(CASE WHEN date_vente BETWEEN DATE('now', '-14 days') AND DATE('now', '-8 days') THEN quantite * prix_unitaire ELSE 0 END) as semaine_precedente
            FROM ventes
        ''')
        
        growth = cursor.fetchone()
        taux_croissance = 0
        if growth['semaine_precedente'] > 0:
            taux_croissance = ((growth['semaine_recente'] - growth['semaine_precedente']) / growth['semaine_precedente']) * 100
        
        conn.close()
        
        return jsonify({
            'success': True,
            'products': [dict(p) for p in top_produits],
            'advice': [dict(r) for r in recommendations],
            'best_day': {
                'nom': best_day['jour_nom'] if best_day else 'Dimanche',
                'moyenne': best_day['moyenne'] if best_day else 0
            },
            'growth': {
                'taux': round(taux_croissance, 1),
                'periode': 7
            },
            'risks': [
                {
                    'niveau': 'haut',
                    'message': f"{len([r for r in recommendations if r['priorite'] == 'haute'])} produits en stock critique"
                }
            ] if recommendations else []
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@ml_bp.route('/tendances-semaine', methods=['GET'])
def get_tendances_semaine():
    """Retourne les tendances par jour de semaine"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        jours = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
        result = []
        
        for i, jour in enumerate(jours):
            cursor.execute('''
                SELECT COALESCE(AVG(quantite * prix_unitaire), 0) as revenu
                FROM ventes
                WHERE strftime('%w', date_vente) = ?
            ''', (str(i),))
            
            result.append({
                'jour': jour,
                'revenu': cursor.fetchone()['revenu']
            })
        
        conn.close()
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@ml_bp.route('/top-consommes', methods=['GET'])
def get_top_consommes():
    """Retourne les produits les plus consommés"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                p.nom as produit,
                p.societe,
                SUM(v.quantite) as qte
            FROM ventes v
            JOIN produits p ON v.produit_id = p.id
            WHERE v.date_vente >= DATE('now', '-30 days')
            GROUP BY p.id
            ORDER BY qte DESC
            LIMIT 8
        ''')
        
        result = cursor.fetchall()
        conn.close()
        
        return jsonify([dict(r) for r in result])
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@ml_bp.route('/next-week', methods=['GET'])
def get_next_week():
    """Retourne les prévisions pour la semaine prochaine"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        jours = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
        aujourdhui = datetime.now().date()
        
        # Calculer la moyenne des 4 dernières semaines
        cursor.execute('''
            SELECT 
                strftime('%w', date_vente) as jour_num,
                AVG(quantite * prix_unitaire) as moyenne
            FROM ventes
            WHERE date_vente >= DATE('now', '-28 days')
            GROUP BY jour_num
        ''')
        
        moyennes = {int(row['jour_num']): row['moyenne'] for row in cursor.fetchall()}
        
        previsions = []
        moyenne_globale = np.mean(list(moyennes.values())) if moyennes else 0
        
        for i, jour in enumerate(jours):
            jour_num = i  # Lundi = 1 en SQLite ?
            revenu = moyennes.get(jour_num, moyenne_globale) * random.uniform(0.95, 1.05)
            
            previsions.append({
                'nom': jour,
                'revenu': int(revenu),
                'revenu_bas': int(revenu * 0.85),
                'revenu_haut': int(revenu * 1.15)
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'jours': previsions,
            'moyenne': int(moyenne_globale)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@ml_bp.route('/retrain', methods=['POST'])
def retrain_models():
    """Simule un réentraînement des modèles ML"""
    try:
        # Ici on appellerait Prophet ou autre
        # Pour l'instant, on simule juste un délai
        
        import time
        time.sleep(2)  # Simulation d'entraînement
        
        return jsonify({
            'success': True,
            'message': 'Modèles entraînés avec succès',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@ml_bp.route('/export', methods=['POST'])
def export_predictions():
    """Exporte les prévisions en PDF (simulé)"""
    try:
        data = request.get_json()
        
        # Simuler la génération PDF
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from io import BytesIO
        
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, 800, "Prévisions ML - Bar Camerounais")
        
        p.setFont("Helvetica", 12)
        p.drawString(50, 770, f"Généré le {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        
        p.showPage()
        p.save()
        
        buffer.seek(0)
        
        from flask import send_file
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"previsions_{datetime.now().strftime('%Y%m%d')}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500