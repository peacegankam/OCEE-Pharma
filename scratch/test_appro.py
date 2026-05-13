import requests
import json

url = "http://localhost:5000/api/appro/"
data = {
    "produit_id": 1,
    "quantite": 10,
    "prix_achat_unitaire": 1500,
    "note": "Test appro from script"
}

try:
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
