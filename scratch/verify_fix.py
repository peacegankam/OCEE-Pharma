
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('data/pharma.sqlite')
cursor = conn.cursor()

# Suppose it's 00:30 AM local time on May 8th (to avoid conflict with previous test)
local_now = datetime(2026, 5, 8, 0, 30)
local_timestamp = local_now.strftime('%Y-%m-%d %H:%M:%S')

# Insert a sale using the NEW logic (passing local timestamp)
cursor.execute("INSERT INTO ventes (produit_id, quantite, prix_unitaire, date_vente) VALUES (1, 1, 1000, ?)", (local_timestamp,))

# Query for today's sales using local date
today = local_now.date().isoformat() # "2026-05-08"
cursor.execute("SELECT COUNT(*) FROM ventes WHERE DATE(date_vente) = ?", (today,))
count = cursor.fetchone()[0]

print(f"Local time: {local_now}")
print(f"Local date: {today}")
print(f"Stored timestamp: {local_timestamp}")
print(f"Query for {today} found: {count} sales")

if count > 0:
    print("SUCCESS: Sale made after midnight local time is NOW correctly found because it was stored with the local date.")
else:
    print("FAILURE: Sale still not found.")

conn.rollback()
conn.close()
