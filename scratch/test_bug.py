import sys
sys.path.append('.')
from database import get_stats_globales, get_stocks_critiques, get_db

try:
    print("Test get_stats_globales()")
    print(get_stats_globales())
except Exception as e:
    print("Exception get_stats_globales:", e)

try:
    print("\nTest get_stocks_critiques()")
    print(get_stocks_critiques())
except Exception as e:
    print("Exception get_stocks_critiques:", e)

try:
    print("\nTest DB query on ventes")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ventes LIMIT 1")
    print(dict(cursor.fetchone()) if cursor.fetchone() else "No ventes")
except Exception as e:
    print("Exception query:", e)
