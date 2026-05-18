import pymysql
import os

# Configuration (identique à config.py)
DB_HOST = 'localhost'
DB_USER = 'root'
DB_PASSWORD = ''
DB_NAME = 'pharma_db'

def fix_negative_stocks():
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = conn.cursor()

        print("--- Correction des stocks négatifs (MySQL) ---")
        
        # 1. Identifier les stocks négatifs
        cursor.execute("SELECT p.nom, s.quantite FROM stocks s JOIN produits p ON s.produit_id = p.id WHERE s.quantite < 0")
        negatifs = cursor.fetchall()
        
        if not negatifs:
            print("Aucun stock négatif trouvé.")
        else:
            for row in negatifs:
                print(f"Correction de {row['nom']} : {row['quantite']} -> 0")
            
            # 2. Mettre à jour les stocks à 0
            cursor.execute("UPDATE stocks SET quantite = 0 WHERE quantite < 0")
            print(f"{cursor.rowcount} lignes mises à jour dans 'stocks'.")

        # 3. Mettre à jour les lots à 0 s'ils sont négatifs
        cursor.execute("UPDATE lots_stock SET quantite_actuelle = 0 WHERE quantite_actuelle < 0")
        if cursor.rowcount > 0:
            print(f"{cursor.rowcount} lots mis à jour dans 'lots_stock'.")

        conn.commit()
        conn.close()
        print("Terminé.")
    except Exception as e:
        print(f"Erreur : {e}")

if __name__ == "__main__":
    fix_negative_stocks()
