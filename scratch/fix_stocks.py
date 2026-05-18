import sqlite3
import os

# Chemin de la base de données
db_path = r'c:\Users\GANKAM PEACE\Desktop\tutorel-main\pharmacie.db'

def fix_negative_stocks():
    if not os.path.exists(db_path):
        print("Base de données non trouvée.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("--- Correction des stocks négatifs ---")
    
    # 1. Identifier les stocks négatifs
    cursor.execute("SELECT p.nom, s.quantite FROM stocks s JOIN produits p ON s.produit_id = p.id WHERE s.quantite < 0")
    negatifs = cursor.fetchall()
    
    if not negatifs:
        print("Aucun stock négatif trouvé.")
    else:
        for nom, qte in negatifs:
            print(f"Correction de {nom} : {qte} -> 0")
        
        # 2. Mettre à jour les stocks à 0
        cursor.execute("UPDATE stocks SET quantite = 0 WHERE quantite < 0")
        print(f"{cursor.rowcount} lignes mises à jour.")

    # 3. Mettre à jour les lots à 0 s'ils sont négatifs
    cursor.execute("UPDATE lots_stock SET quantite_actuelle = 0 WHERE quantite_actuelle < 0")
    if cursor.rowcount > 0:
        print(f"{cursor.rowcount} lots mis à jour.")

    conn.commit()
    conn.close()
    print("Terminé.")

if __name__ == "__main__":
    fix_negative_stocks()
