# routes/ai.py - Assistant IA Médical "ChatGPT Style"
from flask import Blueprint, jsonify, request, session
from database import get_db
import random
import time
import re

ai_bp = Blueprint('ai', __name__)

# Mappage des symptômes vers les conseils/produits
SYMPTOMES = {
    "tête": "Pour les maux de tête, le <b>Paracétamol</b> est le premier choix. Si c'est une migraine forte, l'<b>Ibuprofène</b> peut aider, mais attention à le prendre pendant un repas.",
    "fièvre": "La fièvre se traite généralement avec du <b>Paracétamol</b>. Pensez aussi à bien vous hydrater et à ne pas trop vous couvrir.",
    "ventre": "Pour les douleurs d'estomac, évitez l'aspirine ou l'ibuprofène. Préférez un antispasmodique ou demandez un antiacide si ce sont des brûlures.",
    "gorge": "Pour le mal de gorge, des collutoires ou des pastilles au miel/citron peuvent soulager. Si la déglutition est très douloureuse, consultez pour vérifier s'il s'agit d'une angine bactérienne.",
    "rhume": "Le repos et le lavage de nez à l'eau de mer sont vos meilleurs alliés. La Vitamine C peut aussi aider à renforcer vos défenses.",
    "toux": "S'agit-il d'une toux sèche ou grasse ? Pour une toux sèche, un calmant suffit. Pour une toux grasse, il faut aider à l'expectoration.",
    "fatigue": "Un complexe de <b>Vitamines</b> ou du Magnésium peut vous aider. Pensez aussi à vérifier votre sommeil.",
}

CONSEILS_AUTRES = [
    "D'une manière générale, je vous conseille de toujours lire la notice.",
    "C'est noté. Avez-vous besoin que je vérifie le stock d'un produit en particulier pour cela ?",
    "Je vois. Sachez que je peux aussi vous donner les prix si vous hésitez entre deux marques.",
    "N'oubliez pas que je suis une IA, rien ne remplace le diagnostic final de votre médecin traitant."
]

def chercher_produit_dans_db(nom_partiel):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT p.*, s.quantite FROM produits p LEFT JOIN stocks s ON p.id = s.produit_id WHERE p.nom LIKE ?", (f'%{nom_partiel}%',))
        produit = cursor.fetchone()
        conn.close()
        return dict(produit) if produit else None
    except:
        return None

@ai_bp.route('/chat', methods=['POST'])
def chat():
    """Gère la conversation 'humaine' avec l'IA"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip().lower()
        
        if not message:
            return jsonify({'success': False, 'message': 'Message vide'}), 400

        # Récupérer le contexte du dernier médicament (via session simplifiée dans la réponse pour cet exemple)
        # Note: session nécessite une SECRET_KEY dans app.py (déjà présente)
        dernier_med = session.get('dernier_med')

        res = ""

        # 1. SALUTATIONS ET "YO"
        if any(w in message for w in ["yo", "salut", "bonjour", "ca va", "ça va", "hello"]):
            res = random.choice([
                "Salut ! Comment puis-je t'aider aujourd'hui dans ta pharmacie ?",
                "Bonjour ! Je suis prêt pour tes questions. Un produit à vérifier ou un conseil ?",
                "Yo ! On checke quoi aujourd'hui ? Un prix, un stock, ou un symptôme ?"
            ])

        # 2. GESTION DES SYMPTÔMES (Ex: "et pour les maux de tête ?")
        elif any(s in message for s in SYMPTOMES.keys()):
            for s, conseil in SYMPTOMES.items():
                if s in message:
                    res = conseil
                    break
            # Si c'est un suivi ("et pour...")
            if "et pour" in message or "aussi" in message or "ensuite" in message:
                res = "En ce qui concerne ce symptôme, " + res.lower()

        # 3. QUESTIONS SUR LE PRIX / STOCK
        elif any(w in message for w in ["prix", "coûte", "cout", "tarif", "combien", "stock", "reste", "quantité", "ai-je"]):
            # Chercher un nom de produit dans le message
            m = re.search(r"(?:de|le|du|pour|reste|coûte|prix)\s+([a-z0-9àéèêëîïôûùç-]+)", message)
            nom_produit = m.group(1) if m else None
            
            # Si pas de nom mais qu'on a un contexte
            if not nom_produit and dernier_med:
                nom_produit = dernier_med
                res_intro = f"Pour le <b>{dernier_med.capitalize()}</b> dont on parlait : "
            else:
                res_intro = ""

            if nom_produit:
                p = chercher_produit_dans_db(nom_produit)
                if p:
                    session['dernier_med'] = p['nom'] # On mémorise le contexte
                    qte = p['quantite'] or 0
                    if any(w in message for w in ["prix", "coût", "tarif", "combien"]):
                        res = res_intro + f"Le prix est de <b>{p['prix_vente']:,} FCFA</b> l'unité."
                    else:
                        res = res_intro + f"Il en reste <b>{qte}</b> en stock ({p['unite']})."
                else:
                    res = f"Je ne trouve pas de '{nom_produit}' dans la base. Tu es sûr du nom ?"
            else:
                res = "De quel médicament parles-tu exactement ? Donne-moi son nom pour que je regarde."

        # 4. DOSAGE / CONSEILS PRÉCIS
        elif any(w in message for w in ["dosage", "comment", "prendre", "utilisation"]):
            if "paracétamol" in message or (dernier_med == "paracétamol" and "dosage" in message):
                res = "Pour le <b>Paracétamol</b>, c'est 1g toutes les 6 heures maximum. Pas plus de 4g par jour sinon c'est dangereux pour le foie."
            elif "amox" in message:
                res = "L'<b>Amoxicilline</b> se prend généralement matin et soir. Il faut finir la boîte !"
            elif "ibu" in message:
                res = "L'<b>Ibuprofène</b>, c'est maximum 3 fois par jour, et toujours avec de la nourriture."
            else:
                res = "Pour le dosage, j'ai besoin du nom du produit. Sinon, la règle d'or : toujours demander au pharmacien (c'est toi !) ou lire la notice."

        # 5. REMERCIEMENTS / FIN
        elif any(w in message for w in ["merci", "super", "cool", "top", "ok", "d'accord"]):
            res = random.choice([
                "Pas de souci ! À ton service.",
                "Je t'en prie. Autre chose ?",
                "Nickel. Je suis là si tu as besoin d'un autre check."
            ])

        # 6. DEFAULT (ESSAYER D'ÊTRE PLUS HUMAIN)
        else:
            if dernier_med:
                res = f"Je ne suis pas sûr... Tu veux qu'on continue sur le <b>{dernier_med}</b> ou on passe à autre chose ?"
            else:
                res = "Désolé, je n'ai pas bien saisi. Tu peux me demander le prix ou le stock d'un produit, ou me parler d'un symptôme (tête, ventre, etc.)."

        return jsonify({
            'success': True,
            'response': res,
            'timestamp': time.time()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@ai_bp.route('/suggest', methods=['GET'])
def suggest():
    """Retourne des suggestions intelligentes"""
    suggestions = [
        "Quel est le prix du Doliprane ?",
        "Combien reste-t-il d'Antalgan ?",
        "Donne-moi un conseil médical",
        "Dosage de l'Ibuprofène"
    ]
    return jsonify({'success': True, 'suggestions': random.sample(suggestions, 3)})

