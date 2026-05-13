
import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/pharma.sqlite')
cursor = conn.cursor()

# Get SQLite current timestamp
cursor.execute("SELECT CURRENT_TIMESTAMP")
sqlite_time = cursor.fetchone()[0]

# Get Python local time
python_local_time = datetime.now()
python_utc_time = datetime.utcnow()

print(f"SQLite UTC (CURRENT_TIMESTAMP): {sqlite_time}")
print(f"Python Local: {python_local_time.isoformat()}")
print(f"Python UTC: {python_utc_time.isoformat()}")

# Simulate a sale now
cursor.execute("INSERT INTO ventes (produit_id, quantite, prix_unitaire) VALUES (1, 1, 1000)")
sale_id = cursor.lastrowid
cursor.execute("SELECT date_vente FROM ventes WHERE id = ?", (sale_id,))
sale_time = cursor.fetchone()[0]
print(f"Sale recorded with date_vente: {sale_time}")

# Check if today query finds it
today = python_local_time.date().isoformat()
cursor.execute("SELECT COUNT(*) FROM ventes WHERE DATE(date_vente) = ?", (today,))
count = cursor.fetchone()[0]
print(f"Query for today ({today}) found {count} sales")

conn.rollback()
conn.close()
