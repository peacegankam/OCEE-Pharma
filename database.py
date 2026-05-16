# database.py - Version Multi-DB (SQLite / MySQL)

import sqlite3
import os
import pymysql
from datetime import datetime, timedelta
from config import DB_PATH, SOCIETES, SEUIL_STOCK_DEFAUT, DB_TYPE, DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

class MySQLCursorWrapper:
    """Wrapper pour rendre le curseur MySQL compatible avec la syntaxe SQLite du projet"""
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query, params=None):
        # Remplacement des placeholders ? par %s pour MySQL
        query = query.replace('?', '%s')
        
        # Adaptations de fonctions SQL SQLite -> MySQL
        if "DATE('now')" in query:
            query = query.replace("DATE('now')", "CURDATE()")
        if "strftime('%H'," in query:
            query = query.replace("strftime('%H',", "DATE_FORMAT(")
        if "strftime('%w'," in query:
            # SQLite %w: 0-6 (Dim-Sam) -> MySQL DAYOFWEEK: 1-7 (Dim-Sam)
            query = query.replace("strftime('%w',", "(DAYOFWEEK(")
            query = query.replace("date_vente)", "date_vente) - 1)")
        
        # Adaptation pour le type de champ (SQLite INTEGER PRIMARY KEY AUTOINCREMENT)
        if "INTEGER PRIMARY KEY AUTOINCREMENT" in query:
            query = query.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "INT AUTO_INCREMENT PRIMARY KEY")
        
        return self.cursor.execute(query, params)

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    @property
    def lastrowid(self):
        return self.cursor.lastrowid

    def __iter__(self):
        return iter(self.cursor)

    def close(self):
        self.cursor.close()

class DBProxy:
    """Proxy pour gérer les différences entre SQLite et MySQL"""
    def __init__(self, conn, db_type):
        self.conn = conn
        self.db_type = db_type

    def cursor(self):
        if self.db_type == 'mysql':
            return MySQLCursorWrapper(self.conn.cursor(pymysql.cursors.DictCursor))
        else:
            return self.conn.cursor()

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

def get_db():
    """Retourne une connexion à la base de données configurée"""
    if DB_TYPE == 'mysql':
        try:
            conn = pymysql.connect(
                host=DB_HOST,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                autocommit=True
            )
            return DBProxy(conn, 'mysql')
        except pymysql.err.OperationalError as e:
            if e.args[0] == 1049: # Unknown database
                # Créer la base si elle n'existe pas
                temp_conn = pymysql.connect(
                    host=DB_HOST,
                    user=DB_USER,
                    password=DB_PASSWORD
                )
                with temp_conn.cursor() as cursor:
                    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
                temp_conn.close()
                
                conn = pymysql.connect(
                    host=DB_HOST,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=DB_NAME,
                    autocommit=True
                )
                return DBProxy(conn, 'mysql')
            raise e
    else:
        # SQLite par défaut
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return DBProxy(conn, 'sqlite')

def init_db():
    """Crée toutes les tables si elles n'existent pas"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Adaptation des types pour MySQL
    pk_auto = "INTEGER PRIMARY KEY AUTOINCREMENT" if DB_TYPE == 'sqlite' else "INT AUTO_INCREMENT PRIMARY KEY"
    
    # Table des utilisateurs
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS utilisateurs (
            id {pk_auto},
            nom VARCHAR(255) NOT NULL,
            role VARCHAR(50) NOT NULL DEFAULT 'employe',
            code_pin VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Table des paramètres
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parametres (
            clef VARCHAR(255) PRIMARY KEY,
            valeur TEXT
        )
    ''')
    
    # Table des produits
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS produits (
            id {pk_auto},
            nom VARCHAR(255) NOT NULL,
            societe VARCHAR(255) NOT NULL,
            prix_achat INTEGER NOT NULL,
            prix_vente INTEGER NOT NULL,
            seuil_alerte INTEGER DEFAULT 10,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            date_peremption DATE
        )
    ''')
    
    # Table des stocks
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stocks (
            produit_id INTEGER PRIMARY KEY,
            quantite INTEGER NOT NULL DEFAULT 0,
            derniere_maj TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Table des ventes
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS ventes (
            id {pk_auto},
            produit_id INTEGER NOT NULL,
            quantite INTEGER NOT NULL,
            prix_unitaire INTEGER NOT NULL,
            date_vente TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Table des approvisionnements
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS approvisionnements (
            id {pk_auto},
            produit_id INTEGER NOT NULL,
            quantite INTEGER NOT NULL,
            prix_achat_unitaire INTEGER NOT NULL,
            date_appro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            note TEXT
        )
    ''')
    
    # Table des ajustements de stock
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS historique_stock (
            id {pk_auto},
            produit_id INTEGER NOT NULL,
            quantite_avant INTEGER NOT NULL,
            quantite_apres INTEGER NOT NULL,
            type VARCHAR(50) NOT NULL,
            raison TEXT,
            date_mouvement TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    
    migrate_db()
    insert_test_data_if_empty()
    conn.close()

def migrate_db():
    """Applique les modifications de schéma aux tables existantes"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE ventes ADD COLUMN vendeur_id INTEGER")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE produits ADD COLUMN date_peremption DATE")
    except Exception:
        pass
    conn.commit()
    conn.close()

def insert_test_data_if_empty():
    """Ajoute des données de test pour le développement"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as count FROM produits")
    row = cursor.fetchone()
    count = row['count'] if row else 0
    
    if count == 0:
        print("Insertion des données de test...")
        
        produits = [
            ('Amoxicilline 500mg', 'Antibiotiques', 1500, 2500, 20),
            ('Azithromycine 500mg', 'Antibiotiques', 3000, 5000, 10),
            ('Ciprofloxacine 500mg', 'Antibiotiques', 2000, 3500, 15),
            ('Paracétamol 500mg', 'Analgésiques', 200, 500, 50),
            ('Ibuprofène 400mg', 'Analgésiques', 500, 1200, 30),
            ('Tramadol 50mg', 'Analgésiques', 800, 1500, 15),
            ('Vitamine C 1000mg', 'Vitamines', 1500, 2800, 25),
            ('Multivitamines', 'Vitamines', 3500, 6000, 10),
            ('Calcium + D3', 'Vitamines', 2500, 4500, 15),
            ('Betamethasone Crème', 'Dermatologie', 1200, 2200, 20),
            ('Sélénium Shampooing', 'Dermatologie', 4500, 7500, 10),
            ('Crème Hydratante', 'Dermatologie', 3000, 5500, 15),
            ('Thermomètre Digital', 'Matériel Médical', 1500, 3500, 10),
            ('Tensiomètre Brassard', 'Matériel Médical', 15000, 25000, 5),
            ('Pansements Autocollants', 'Matériel Médical', 500, 1000, 40)
        ]
        
        import random
        for p in produits:
            cursor.execute('''
                INSERT INTO produits (nom, societe, prix_achat, prix_vente, seuil_alerte)
                VALUES (?, ?, ?, ?, ?)
            ''', p)
            
            produit_id = cursor.lastrowid
            stock_init = random.randint(50, 200)
            cursor.execute('''
                INSERT INTO stocks (produit_id, quantite)
                VALUES (?, ?)
            ''', (produit_id, stock_init))
        
        conn.commit()
    
    cursor.execute("SELECT COUNT(*) as count FROM utilisateurs")
    row_user = cursor.fetchone()
    if row_user and row_user['count'] == 0:
        cursor.execute("INSERT INTO utilisateurs (nom, role, code_pin) VALUES ('Gérant', 'admin', '1234')")
        cursor.execute("INSERT INTO utilisateurs (nom, role, code_pin) VALUES ('Alice (Caisse 1)', 'employe', '0000')")
        cursor.execute("INSERT INTO parametres (clef, valeur) VALUES ('NOM_BAR', 'OCEE')")
        conn.commit()
        print("Utilisateurs par défaut créés.")
    
    conn.close()

# Fonctions utilitaires adaptées

def get_produits_with_stock():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.*, s.quantite as stock_actuel
        FROM produits p
        LEFT JOIN stocks s ON p.id = s.produit_id
        ORDER BY p.societe, p.nom
    ''')
    result = cursor.fetchall()
    conn.close()
    return result

def get_ventes_aujourdhui():
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.now().date()
    cursor.execute('''
        SELECT v.*, p.nom, p.societe
        FROM ventes v
        JOIN produits p ON v.produit_id = p.id
        WHERE DATE(REPLACE(v.date_vente, 'T', ' ')) = ?
        ORDER BY v.date_vente DESC
    ''', (today.isoformat(),))
    result = cursor.fetchall()
    conn.close()
    return result

def get_stats_globales():
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.now().date()
    
    cursor.execute('''
        SELECT COALESCE(SUM(v.quantite * v.prix_unitaire), 0) as total
        FROM ventes v
        WHERE DATE(REPLACE(v.date_vente, 'T', ' ')) = ?
    ''', (today.isoformat(),))
    row = cursor.fetchone()
    revenus_jour = row['total'] if row else 0
    
    cursor.execute('''
        SELECT COALESCE(SUM(v.quantite), 0) as total
        FROM ventes v
        WHERE DATE(REPLACE(v.date_vente, 'T', ' ')) = ?
    ''', (today.isoformat(),))
    row = cursor.fetchone()
    ventes_jour = row['total'] if row else 0
    
    cursor.execute('''
        SELECT COALESCE(SUM(v.quantite * (v.prix_unitaire - p.prix_achat)), 0) as benefice
        FROM ventes v
        JOIN produits p ON v.produit_id = p.id
        WHERE DATE(REPLACE(v.date_vente, 'T', ' ')) = ?
    ''', (today.isoformat(),))
    row = cursor.fetchone()
    benefice_jour = row['benefice'] if row else 0
    
    cursor.execute('''
        SELECT COUNT(*) as count
        FROM stocks s
        JOIN produits p ON s.produit_id = p.id
        WHERE s.quantite <= p.seuil_alerte
    ''')
    row = cursor.fetchone()
    alertes_stock = row['count'] if row else 0
    
    conn.close()
    return {
        'revenus_jour': revenus_jour,
        'ventes_jour': ventes_jour,
        'benefice_jour': benefice_jour,
        'alertes_stock': alertes_stock
    }

def get_revenus_semaine():
    conn = get_db()
    cursor = conn.cursor()
    dates = []
    revenus = []
    for i in range(6, -1, -1):
        date = (datetime.now() - timedelta(days=i)).date()
        dates.append(date.strftime('%d/%m'))
        cursor.execute('''
            SELECT COALESCE(SUM(quantite * prix_unitaire), 0) as total
            FROM ventes
            WHERE DATE(REPLACE(date_vente, 'T', ' ')) = ?
        ''', (date.isoformat(),))
        row = cursor.fetchone()
        revenus.append(row['total'] if row else 0)
    conn.close()
    return [{'date': d, 'revenu': r} for d, r in zip(dates, revenus)]

def get_top_produits(limit=5):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.nom, SUM(v.quantite * v.prix_unitaire) as revenus
        FROM ventes v
        JOIN produits p ON v.produit_id = p.id
        GROUP BY p.id, p.nom
        ORDER BY revenus DESC
        LIMIT ?
    ''', (limit,))
    result = cursor.fetchall()
    conn.close()
    return result

def get_repartition_societes():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.societe, SUM(v.quantite * v.prix_unitaire) as revenus
        FROM ventes v
        JOIN produits p ON v.produit_id = p.id
        GROUP BY p.societe
        ORDER BY revenus DESC
    ''')
    result = cursor.fetchall()
    conn.close()
    return result

def get_revenus_mensuel(year=None, month=None):
    """Retourne le total des revenus pour le mois demandé (ou mois courant)."""
    conn = get_db()
    cursor = conn.cursor()
    from datetime import datetime, timedelta
    today = datetime.now().date()
    if year is None or month is None:
        year = today.year
        month = today.month

    # Première journée du mois
    debut = datetime(year, month, 1).date()
    # Premier jour du mois suivant
    if month == 12:
        suivant = datetime(year + 1, 1, 1).date()
    else:
        suivant = datetime(year, month + 1, 1).date()

    cursor.execute('''
        SELECT COALESCE(SUM(quantite * prix_unitaire), 0) as total
        FROM ventes
        WHERE DATE(date_vente) >= ? AND DATE(date_vente) < ?
    ''', (debut.isoformat(), suivant.isoformat()))

    row = cursor.fetchone()
    total = row['total'] if row else 0
    conn.close()
    return total

def get_revenus_total():
    """Retourne le total cumulé des revenus depuis le début des enregistrements."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COALESCE(SUM(quantite * prix_unitaire), 0) as total
        FROM ventes
    ''')
    row = cursor.fetchone()
    total = row['total'] if row else 0
    conn.close()
    return total

def get_stocks_critiques():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.id, p.nom, p.societe, s.quantite, p.seuil_alerte
        FROM stocks s
        JOIN produits p ON s.produit_id = p.id
        WHERE s.quantite <= p.seuil_alerte
        ORDER BY (s.quantite * 1.0 / p.seuil_alerte) ASC
    ''')
    result = cursor.fetchall()
    conn.close()
    return result

# Initialisation
init_db()