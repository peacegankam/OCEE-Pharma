import pymysql

# Configuration
DB_HOST = 'localhost'
DB_USER = 'root'
DB_PASSWORD = ''
DB_NAME = 'pharma_db'

def fix_migration_dates():
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()

        print("--- Correction des dates de réception des lots migrés ---")
        
        # Mettre les lots initiaux dans le passé pour qu'ils ne polluent pas le rapport d'aujourd'hui
        query = "UPDATE lots_stock SET date_reception = '2000-01-01 00:00:00' WHERE reference_lot = 'LOT_INITIAL'"
        cursor.execute(query)
        
        print(f"{cursor.rowcount} lots mis à jour.")

        conn.commit()
        conn.close()
        print("Terminé.")
    except Exception as e:
        print(f"Erreur : {e}")

if __name__ == "__main__":
    fix_migration_dates()
