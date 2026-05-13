# routes/rapports.py - Routes pour les rapports PDF/exports
from flask import Blueprint, jsonify, request, send_file
from database import get_db
from datetime import datetime, timedelta
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from io import BytesIO
import json

rapports_bp = Blueprint('rapports', __name__)

@rapports_bp.route('/journalier-json', methods=['GET'])
def rapport_journalier_json():
    """Retourne les données JSON pour le rapport journalier"""
    try:
        date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Ventes du jour
        cursor.execute('''
            SELECT 
                strftime('%H:%M', v.date_vente) as heure,
                p.nom as produit,
                p.societe,
                v.quantite,
                v.prix_unitaire,
                (v.quantite * v.prix_unitaire) as montant_total
            FROM ventes v
            JOIN produits p ON v.produit_id = p.id
            WHERE DATE(v.date_vente) = ?
            ORDER BY v.date_vente ASC
        ''', (date_str,))
        ventes = [dict(row) for row in cursor.fetchall()]
        
        # Totaux ventes
        cursor.execute('''
            SELECT 
                COUNT(*) as nb_ventes,
                COALESCE(SUM(v.quantite * v.prix_unitaire), 0) as revenus,
                COALESCE(SUM(v.quantite * p.prix_achat), 0) as cout_produits,
                COALESCE(SUM(v.quantite * (v.prix_unitaire - p.prix_achat)), 0) as benefice
            FROM ventes v
            JOIN produits p ON v.produit_id = p.id
            WHERE DATE(v.date_vente) = ?
        ''', (date_str,))
        stats_ventes = dict(cursor.fetchone())
        
        # Approvisionnements du jour
        cursor.execute('''
            SELECT 
                strftime('%H:%M', a.date_appro) as heure,
                p.nom as produit,
                p.societe,
                a.quantite,
                (a.quantite * a.prix_achat_unitaire) as cout_total
            FROM approvisionnements a
            JOIN produits p ON a.produit_id = p.id
            WHERE DATE(a.date_appro) = ?
            ORDER BY a.date_appro ASC
        ''', (date_str,))
        appros = [dict(row) for row in cursor.fetchall()]
        
        # Total dépenses appro
        cursor.execute('''
            SELECT COALESCE(SUM(quantite * prix_achat_unitaire), 0) as depenses_appro
            FROM approvisionnements
            WHERE DATE(date_appro) = ?
        ''', (date_str,))
        depenses_appro = cursor.fetchone()['depenses_appro']
        
        # Ventes par société
        cursor.execute('''
            SELECT 
                p.societe,
                COUNT(*) as nb_ventes,
                SUM(v.quantite) as qte_totale,
                SUM(v.quantite * v.prix_unitaire) as revenus
            FROM ventes v
            JOIN produits p ON v.produit_id = p.id
            WHERE DATE(v.date_vente) = ?
            GROUP BY p.societe
        ''', (date_str,))
        par_societe = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'date': date_str,
            **stats_ventes,
            'depenses_appro': depenses_appro,
            'ventes': ventes,
            'approvisionnements': appros,
            'par_societe': par_societe
        })
        
    except Exception as e:
        print(f"Erreur rapport JSON: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@rapports_bp.route('/journalier', methods=['GET'])
def rapport_journalier():
    """Génère le rapport PDF journalier pour le pharmacien"""
    try:
        date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Récupérer les ventes du jour
        cursor.execute('''
            SELECT 
                v.*,
                p.nom,
                p.societe,
                p.prix_achat,
                (v.prix_unitaire - p.prix_achat) as marge_unitaire
            FROM ventes v
            JOIN produits p ON v.produit_id = p.id
            WHERE DATE(v.date_vente) = ?
            ORDER BY v.date_vente ASC
        ''', (date_str,))
        
        ventes = cursor.fetchall()
        
        # Calculer les totaux
        cursor.execute('''
            SELECT 
                COUNT(*) as nb_ventes,
                COALESCE(SUM(v.quantite), 0) as total_articles,
                COALESCE(SUM(v.quantite * v.prix_unitaire), 0) as total_ventes,
                COALESCE(SUM(v.quantite * (v.prix_unitaire - p.prix_achat)), 0) as total_benefice
            FROM ventes v
            JOIN produits p ON v.produit_id = p.id
            WHERE DATE(v.date_vente) = ?
        ''', (date_str,))
        
        totals = cursor.fetchone()
        
        # Récupérer les approvisionnements du jour
        cursor.execute('''
            SELECT 
                a.*,
                p.nom,
                (a.quantite * a.prix_achat_unitaire) as total
            FROM approvisionnements a
            JOIN produits p ON a.produit_id = p.id
            WHERE DATE(a.date_appro) = ?
            ORDER BY a.date_appro ASC
        ''', (date_str,))
        
        appros = cursor.fetchall()
        
        conn.close()
        
        # Générer le PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []
        
        # Titre
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            alignment=1,  # Centre
            spaceAfter=20
        )
        
        date_formatee = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d/%m/%Y')
        elements.append(Paragraph(f"Rapport Journalier - {date_formatee}", title_style))
        elements.append(Spacer(1, 0.5*cm))
        
        # Résumé
        elements.append(Paragraph(f"<b>Résumé du jour</b>", styles['Heading2']))
        
        summary_data = [
            ['Total ventes', f"{totals['total_ventes']:,.0f} FCFA"],
            ['Bénéfice', f"{totals['total_benefice']:,.0f} FCFA"],
            ['Nombre de ventes', str(totals['nb_ventes'])],
            ['Articles vendus', str(totals['total_articles'])],
        ]
        
        if appros:
            total_appro = sum(a['total'] for a in appros)
            summary_data.append(['Dépenses appro.', f"{total_appro:,.0f} FCFA"])
            summary_data.append(['Solde attendu', f"{totals['total_ventes'] - total_appro:,.0f} FCFA"])
        
        summary_table = Table(summary_data, colWidths=[4*cm, 4*cm])
        summary_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 1*cm))
        
        # Détail des ventes
        if ventes:
            elements.append(Paragraph(f"<b>Détail des ventes</b>", styles['Heading2']))
            
            vente_data = [['Heure', 'Produit', 'Qté', 'Prix', 'Total']]
            for v in ventes:
                vente_data.append([
                    v['date_vente'][11:16],  # Heure
                    f"{v['nom']} ({v['societe']})",
                    str(v['quantite']),
                    f"{v['prix_unitaire']:,.0f}",
                    f"{(v['quantite'] * v['prix_unitaire']):,.0f}"
                ])
            
            vente_table = Table(vente_data, colWidths=[3*cm, 6*cm, 2*cm, 3*cm, 3*cm])
            vente_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ]))
            elements.append(vente_table)
            elements.append(Spacer(1, 1*cm))
        
        # Approvisionnements
        if appros:
            elements.append(Paragraph(f"<b>Approvisionnements</b>", styles['Heading2']))
            
            appro_data = [['Heure', 'Produit', 'Qté', 'Prix unit.', 'Total']]
            for a in appros:
                appro_data.append([
                    a['date_appro'][11:16],
                    a['nom'],
                    str(a['quantite']),
                    f"{a['prix_achat_unitaire']:,.0f}",
                    f"{a['total']:,.0f}"
                ])
            
            appro_table = Table(appro_data, colWidths=[3*cm, 6*cm, 2*cm, 3*cm, 3*cm])
            appro_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ]))
            elements.append(appro_table)
        
        # Construire le PDF
        doc.build(elements)
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"rapport_journalier_{date_str}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@rapports_bp.route('/bilan', methods=['GET'])
def bilan_periode():
    """Génère un bilan PDF pour une période"""
    try:
        debut = request.args.get('debut')
        fin = request.args.get('fin')
        
        if not debut or not fin:
            return jsonify({'success': False, 'message': 'Paramètres debut et fin requis'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Ventes sur la période
        cursor.execute('''
            SELECT 
                DATE(v.date_vente) as date,
                COUNT(*) as nb_ventes,
                SUM(v.quantite) as articles,
                SUM(v.quantite * v.prix_unitaire) as revenu,
                SUM(v.quantite * (v.prix_unitaire - p.prix_achat)) as benefice
            FROM ventes v
            JOIN produits p ON v.produit_id = p.id
            WHERE DATE(v.date_vente) BETWEEN ? AND ?
            GROUP BY DATE(v.date_vente)
            ORDER BY date ASC
        ''', (debut, fin))
        
        ventes = cursor.fetchall()
        
        # Top produits
        cursor.execute('''
            SELECT 
                p.nom,
                p.societe,
                SUM(v.quantite) as quantite,
                SUM(v.quantite * v.prix_unitaire) as revenu
            FROM ventes v
            JOIN produits p ON v.produit_id = p.id
            WHERE DATE(v.date_vente) BETWEEN ? AND ?
            GROUP BY p.id
            ORDER BY revenu DESC
            LIMIT 10
        ''', (debut, fin))
        
        top_produits = cursor.fetchall()
        
        # Répartition par société
        cursor.execute('''
            SELECT 
                p.societe,
                SUM(v.quantite * v.prix_unitaire) as revenu
            FROM ventes v
            JOIN produits p ON v.produit_id = p.id
            WHERE DATE(v.date_vente) BETWEEN ? AND ?
            GROUP BY p.societe
            ORDER BY revenu DESC
        ''', (debut, fin))
        
        societes = cursor.fetchall()
        
        conn.close()
        
        # Générer PDF (similaire au rapport journalier mais avec période)
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []
        
        # Titre
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            alignment=1,
            spaceAfter=20
        )
        
        elements.append(Paragraph(f"Bilan du {debut} au {fin}", title_style))
        elements.append(Spacer(1, 0.5*cm))
        
        # Totaux
        total_revenu = sum(v['revenu'] for v in ventes)
        total_benefice = sum(v['benefice'] for v in ventes)
        
        summary_data = [
            ['Période', f"{debut} au {fin}"],
            ['Total revenus', f"{total_revenu:,.0f} FCFA"],
            ['Total bénéfice', f"{total_benefice:,.0f} FCFA"],
            ['Marge brute', f"{(total_benefice/total_revenu*100):.1f}%" if total_revenu > 0 else "0%"],
        ]
        
        summary_table = Table(summary_data, colWidths=[4*cm, 6*cm])
        summary_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 1*cm))
        
        # Top produits
        if top_produits:
            elements.append(Paragraph("<b>Top 10 produits</b>", styles['Heading2']))
            
            top_data = [['Produit', 'Société', 'Qté', 'Revenu']]
            for p in top_produits:
                top_data.append([
                    p['nom'],
                    p['societe'],
                    str(p['quantite']),
                    f"{p['revenu']:,.0f} FCFA"
                ])
            
            top_table = Table(top_data, colWidths=[5*cm, 3*cm, 2*cm, 4*cm])
            top_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
                ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ]))
            elements.append(top_table)
        
        doc.build(elements)
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"bilan_{debut}_au_{fin}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500