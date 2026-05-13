import sqlite3
conn = sqlite3.connect('data/pharma.sqlite')
cursor = conn.cursor()
cursor.execute("UPDATE parametres SET valeur='OCEE PHARMA' WHERE clef='NOM_BAR'")
conn.commit()
conn.close()
print("Base de données mise à jour avec succès : OCEE PHARMA")
