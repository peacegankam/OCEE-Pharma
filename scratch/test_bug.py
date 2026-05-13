
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('data/pharma.sqlite')
cursor = conn.cursor()

# Suppose it's 00:30 AM local time on May 7th
# Local time: 2026-05-07 00:30:00
# UTC time (if offset is +1): 2026-05-06 23:30:00

local_now = datetime(2026, 5, 7, 0, 30)
utc_equivalent = "2026-05-06 23:30:00"

# Insert a sale with UTC time (as SQLite CURRENT_TIMESTAMP would)
cursor.execute("INSERT INTO ventes (produit_id, quantite, prix_unitaire, date_vente) VALUES (1, 1, 1000, ?)", (utc_equivalent,))

# Query for today's sales using local date
today = local_now.date().isoformat() # "2026-05-07"
cursor.execute("SELECT COUNT(*) FROM ventes WHERE DATE(date_vente) = ?", (today,))
count = cursor.fetchone()[0]

print(f"Local time: {local_now}")
print(f"Local date: {today}")
print(f"Stored UTC time: {utc_equivalent}")
print(f"Query for {today} found: {count} sales")

if count == 0:
    print("BUG REPRODUCED: Sale made after midnight local time is not found in today's report because it was stored with yesterday's UTC date.")

conn.rollback()
conn.close()
