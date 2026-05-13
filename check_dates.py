from datetime import datetime
import sqlite3

conn = sqlite3.connect('data/pharma.sqlite')
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute("SELECT id, date_vente FROM ventes ORDER BY id DESC LIMIT 5")
rows = c.fetchall()
print("=== Dernières ventes en base ===")
for r in rows:
    print(dict(r))
print("Local now:", datetime.now().isoformat())
print("Local date:", datetime.now().date().isoformat())
conn.close()
