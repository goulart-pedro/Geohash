import csv


def load_restaurants(path="data/restaurantes.csv"):
    """Carrega o CSV gerado por scripts/geocodificar_bares.py."""
    restaurants = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            restaurants.append({
                "id": int(row["id"]),
                "name": row["nome"],
                "address": row["endereco"],
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
            })
    return restaurants
