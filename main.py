import html
import os

import dash_leaflet.express as dlx
from dash import Dash

from callbacks import register_callbacks
from layout import get_layout
from utils.fleet import Fleet
from utils.load_data import load_restaurants
from utils.road_snap import RoadSnapper
from utils.synthetic import start_fleet_job

BHZ = (-19.9102, -43.9266)
DEFAULTS = {"n": 500, "sigma": 500.0, "radius": 2.0, "speed": 25.0, "max_n": 50000}
RESTAURANTS_CSV = os.path.join("data", "restaurantes.csv")

if not os.path.exists(RESTAURANTS_CSV):
    raise SystemExit(
        f"{RESTAURANTS_CSV} não encontrado.\n"
        "Gere-o com:  python scripts/geocodificar_bares.py --limite 200\n"
        "(requer data/bares.csv)."
    )

restaurants = load_restaurants(RESTAURANTS_CSV)
print(f"{len(restaurants)} restaurantes carregados.")

fleet = Fleet()
snapper = RoadSnapper()

restaurants_geojson = dlx.dicts_to_geojson([
    {"lat": r["lat"], "lon": r["lon"], "rid": r["id"],
     "popup": f"<b>{html.escape(r['name'])}</b><br>{html.escape(r['address'])}"}
    for r in restaurants
])

app = Dash(__name__, title="Entregadores mais próximos")
app.layout = get_layout(restaurants, restaurants_geojson, BHZ, DEFAULTS)
register_callbacks(app, restaurants, fleet, snapper, DEFAULTS)
server = app.server      # usado pelo gunicorn: gunicorn main:server


snapper.start()                       # malha carregada em background (log no terminal)
start_fleet_job(restaurants, fleet, snapper, DEFAULTS["n"], DEFAULTS["sigma"])

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 8050)))
