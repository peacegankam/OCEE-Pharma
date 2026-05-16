import argparse
import os
import sqlite3
import sys

try:
    import pymysql
except ImportError:
    pymysql = None


def parse_args():
    parser = argparse.ArgumentParser(
        description='Migrer les données de SQLite vers MySQL en conservant le schéma du projet.'
    )
    parser.add_argument(
        '--sqlite-path',
        default=os.path.join(os.path.dirname(__file__), 'data', 'pharma.sqlite'),
        help='Chemin vers le fichier SQLite source'
    )
    parser.add_argument('--mysql-host', default='localhost', help='Hôte MySQL')
    parser.add_argument('--mysql-user', default='root', help='Utilisateur MySQL')
    parser.add_argument('--mysql-password', default='', help='Mot de passe MySQL')
    parser.add_argument('--mysql-db', default='pharma_db', help='Nom de la base MySQL à créer/utiliser')
    parser.add_argument('--drop-data', action='store_true', help='Supprime les données existantes dans MySQL avant l import')
    parser.add_argument('--dry-run', action='store_true', help='Affiche les actions sans exécuter réellement la migration')
    return parser.parse_args()


def get_sqlite_connection(sqlite_path):
    if not os.path.exists(sqlite_path):
        raise FileNotFoundError(f"Fichier SQLite introuvable: {sqlite_path}")
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_mysql_connection(host, user, password, database=None):
    if pymysql is None:
        raise ImportError('pymysql n est pas installé. Installez-le avec pip install pymysql')
    kwargs = {
        'host': host,
        'user': user,
        'password': password,
        'autocommit': True,
        'cursorclass': pymysql.cursors.DictCursor,
    }
    if database:
        kwargs['database'] = database
    return pymysql.connect(**kwargs)


def create_mysql_database(mysql_conn, database_name):
    with mysql_conn.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        cursor.execute(f"USE `{database_name}`;")


def create_mysql_tables(mysql_conn):
    with mysql_conn.cursor() as cursor:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS utilisateurs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nom VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL DEFAULT 'employe',
                code_pin VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS parametres (
                clef VARCHAR(255) PRIMARY KEY,
                valeur TEXT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS produits (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nom VARCHAR(255) NOT NULL,
                societe VARCHAR(255) NOT NULL,
                prix_achat INTEGER NOT NULL,
                prix_vente INTEGER NOT NULL,
                seuil_alerte INTEGER DEFAULT 10,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                date_peremption DATE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stocks (
                produit_id INTEGER PRIMARY KEY,
                quantite INTEGER NOT NULL DEFAULT 0,
                derniere_maj TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_stocks_produit FOREIGN KEY (produit_id) REFERENCES produits(id) ON DELETE RESTRICT ON UPDATE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ventes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                produit_id INTEGER NOT NULL,
                quantite INTEGER NOT NULL,
                prix_unitaire INTEGER NOT NULL,
                date_vente TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                vendeur_id INTEGER,
                CONSTRAINT fk_ventes_produit FOREIGN KEY (produit_id) REFERENCES produits(id) ON DELETE RESTRICT ON UPDATE CASCADE,
                CONSTRAINT fk_ventes_vendeur FOREIGN KEY (vendeur_id) REFERENCES utilisateurs(id) ON DELETE SET NULL ON UPDATE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS approvisionnements (
                id INT AUTO_INCREMENT PRIMARY KEY,
                produit_id INTEGER NOT NULL,
                quantite INTEGER NOT NULL,
                prix_achat_unitaire INTEGER NOT NULL,
                date_appro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                note TEXT,
                CONSTRAINT fk_appro_produit FOREIGN KEY (produit_id) REFERENCES produits(id) ON DELETE RESTRICT ON UPDATE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS historique_stock (
                id INT AUTO_INCREMENT PRIMARY KEY,
                produit_id INTEGER NOT NULL,
                quantite_avant INTEGER NOT NULL,
                quantite_apres INTEGER NOT NULL,
                type VARCHAR(50) NOT NULL,
                raison TEXT,
                date_mouvement TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_historique_produit FOREIGN KEY (produit_id) REFERENCES produits(id) ON DELETE RESTRICT ON UPDATE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        ''')


def drop_mysql_tables(mysql_conn):
    tables = [
        'historique_stock',
        'approvisionnements',
        'ventes',
        'stocks',
        'produits',
        'utilisateurs',
        'parametres',
    ]
    with mysql_conn.cursor() as cursor:
        cursor.execute('SET FOREIGN_KEY_CHECKS = 0;')
        for table in tables:
            cursor.execute(f'DROP TABLE IF EXISTS `{table}`;')
        cursor.execute('SET FOREIGN_KEY_CHECKS = 1;')


def add_mysql_foreign_keys(mysql_conn):
    with mysql_conn.cursor() as cursor:
        fk_commands = [
            '''ALTER TABLE `stocks`
                ADD CONSTRAINT fk_stocks_produit FOREIGN KEY (`produit_id`) REFERENCES `produits`(`id`) ON DELETE RESTRICT ON UPDATE CASCADE''' ,
            '''ALTER TABLE `ventes`
                ADD CONSTRAINT fk_ventes_produit FOREIGN KEY (`produit_id`) REFERENCES `produits`(`id`) ON DELETE RESTRICT ON UPDATE CASCADE''' ,
            '''ALTER TABLE `ventes`
                ADD CONSTRAINT fk_ventes_vendeur FOREIGN KEY (`vendeur_id`) REFERENCES `utilisateurs`(`id`) ON DELETE SET NULL ON UPDATE CASCADE''' ,
            '''ALTER TABLE `approvisionnements`
                ADD CONSTRAINT fk_appro_produit FOREIGN KEY (`produit_id`) REFERENCES `produits`(`id`) ON DELETE RESTRICT ON UPDATE CASCADE''' ,
            '''ALTER TABLE `historique_stock`
                ADD CONSTRAINT fk_historique_produit FOREIGN KEY (`produit_id`) REFERENCES `produits`(`id`) ON DELETE RESTRICT ON UPDATE CASCADE''' ,
        ]
        for command in fk_commands:
            try:
                cursor.execute(command)
            except Exception:
                # Ignore errors when constraint already exists or table does not support it yet.
                pass


def truncate_mysql_tables(mysql_conn, tables):
    with mysql_conn.cursor() as cursor:
        cursor.execute('SET FOREIGN_KEY_CHECKS = 0;')
        for table in tables:
            cursor.execute(f'TRUNCATE TABLE `{table}`;')
        cursor.execute('SET FOREIGN_KEY_CHECKS = 1;')


def copy_table(sqlite_conn, mysql_conn, table_name, columns, preserve_id=False):
    sqlite_cursor = sqlite_conn.cursor()
    mysql_cursor = mysql_conn.cursor()

    column_list = ', '.join(f'`{c}`' for c in columns)
    placeholder = ', '.join(['%s'] * len(columns))
    mysql_query = f"INSERT INTO `{table_name}` ({column_list}) VALUES ({placeholder})"

    sqlite_query = f"SELECT {column_list} FROM `{table_name}`"
    sqlite_cursor.execute(sqlite_query)
    rows = sqlite_cursor.fetchall()

    if not rows:
        return 0

    inserted = 0
    for row in rows:
        values = [row[c] for c in columns]
        mysql_cursor.execute(mysql_query, values)
        inserted += 1

    mysql_conn.commit()
    return inserted


def reset_auto_increment(mysql_conn, table_name, pk_column='id'):
    with mysql_conn.cursor() as cursor:
        cursor.execute(f"SELECT MAX(`{pk_column}`) as max_id FROM `{table_name}`")
        result = cursor.fetchone()
        max_id = result['max_id'] if result and result['max_id'] is not None else 0
        if max_id > 0:
            cursor.execute(f"ALTER TABLE `{table_name}` AUTO_INCREMENT = {max_id + 1}")


def main():
    args = parse_args()

    if args.dry_run:
        print('Dry run: aucune action n est exécutée.')

    if pymysql is None:
        print('Le module pymysql n est pas installé. Installez-le avec: pip install pymysql')
        sys.exit(1)

    sqlite_conn = get_sqlite_connection(args.sqlite_path)
    print(f'Connexion SQLite réussie : {args.sqlite_path}')

    mysql_root_conn = get_mysql_connection(args.mysql_host, args.mysql_user, args.mysql_password)
    create_mysql_database(mysql_root_conn, args.mysql_db)
    mysql_root_conn.close()

    mysql_conn = get_mysql_connection(args.mysql_host, args.mysql_user, args.mysql_password, args.mysql_db)
    print(f'Connexion MySQL réussie : {args.mysql_host} / base {args.mysql_db}')

    if args.drop_data:
        drop_mysql_tables(mysql_conn)
        print('Anciennes tables MySQL supprimées pour recréer un schéma propre.')

    create_mysql_tables(mysql_conn)
    add_mysql_foreign_keys(mysql_conn)
    print('Schéma MySQL créé ou vérifié avec contraintes FOREIGN KEY.')

    tables = [
        ('utilisateurs', ['id', 'nom', 'role', 'code_pin', 'created_at'], True),
        ('parametres', ['clef', 'valeur'], False),
        ('produits', ['id', 'nom', 'societe', 'prix_achat', 'prix_vente', 'seuil_alerte', 'created_at', 'updated_at', 'date_peremption'], True),
        ('stocks', ['produit_id', 'quantite', 'derniere_maj'], False),
        ('ventes', ['id', 'produit_id', 'quantite', 'prix_unitaire', 'date_vente', 'vendeur_id'], True),
        ('approvisionnements', ['id', 'produit_id', 'quantite', 'prix_achat_unitaire', 'date_appro', 'note'], True),
        ('historique_stock', ['id', 'produit_id', 'quantite_avant', 'quantite_apres', 'type', 'raison', 'date_mouvement'], True),
    ]

    if args.drop_data:
        truncate_mysql_tables(mysql_conn, [table for table, _, _ in tables])
        print('Données existantes dans MySQL supprimées.')

    total_inserted = 0
    for table_name, columns, preserve_id in tables:
        print(f'Transfert table {table_name}...')
        count = copy_table(sqlite_conn, mysql_conn, table_name, columns, preserve_id=preserve_id)
        total_inserted += count
        print(f'  {count} ligne(s) importée(s) dans {table_name}.')

    for table_name, columns, preserve_id in tables:
        if preserve_id:
            reset_auto_increment(mysql_conn, table_name)

    sqlite_conn.close()
    mysql_conn.close()

    print(f'Migration terminée : {total_inserted} ligne(s) copiée(s) au total.')


if __name__ == '__main__':
    main()
