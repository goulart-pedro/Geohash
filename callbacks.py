import math
from html import escape

import dash_leaflet as dl
import dash_leaflet.express as dlx
from dash import Input, Output, State, ctx, html, no_update

from utils.geohash import decode_bbox
from utils.synthetic import start_fleet_job

COLOR_RESTAURANT = "#3498db"
COLOR_INSIDE = "#e53935"
COLOR_OUTSIDE = "#9e9e9e"
EMPTY_GEOJSON = {"type": "FeatureCollection", "features": []}


def _clamp_float(value, lo, hi, default):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(v):
        return default
    return max(lo, min(hi, v))


def _num(x, nd=2):
    return f"{x:.{nd}f}".replace(".", ",")


def _card(label, value, sub=None, accent=None):
    children = [html.Div(label, className="metric-label"),
                html.Div(value, className="metric-value",
                         style={"color": accent} if accent else None)]
    if sub:
        children.append(html.Div(sub, className="metric-sub"))
    return html.Div(children, className="metric-card")


def _message(text):
    return [html.Div(text, className="metrics-empty")]


def register_callbacks(app, restaurants, fleet, snapper, defaults):
    by_id = {r["id"]: r for r in restaurants}

    # ------------------------------------------------------------------ frota
    @app.callback(
        Output("fleet-signal", "data"),
        Output("status", "children"),
        Input("btn-generate", "n_clicks"),
        Input("poll", "n_intervals"),
        State("n-input", "value"),
        State("sigma-input", "value"),
        State("fleet-signal", "data"),
        prevent_initial_call=True,
    )
    def sync_fleet(_clicks, _ticks, n, sigma, current):
        if ctx.triggered_id == "btn-generate":
            n = int(_clamp_float(n, 1, defaults["max_n"], defaults["n"]))
            sigma = _clamp_float(sigma, 20, 5000, defaults["sigma"])
            if not start_fleet_job(restaurants, fleet, snapper, n, sigma):
                return no_update, "Já existe uma geração em andamento…"
            return no_update, fleet.status_text
        # a consulta é refeita só quando uma nova frota fica pronta
        ready = fleet.version != current and not fleet.busy
        return (fleet.version if ready else no_update), fleet.status_text

    # ------------------------------------------------- seleção pelo clique no mapa
    @app.callback(
        Output("restaurant-dropdown", "value"),
        Input("restaurants-layer", "clickData"),
        prevent_initial_call=True,
    )
    def select_from_map(click):
        try:
            rid = click["properties"].get("rid")
        except (TypeError, KeyError, AttributeError):
            return no_update
        return rid if rid in by_id else no_update

    # ----------------------------------------------------------------- consulta
    @app.callback(
        Output("couriers-layer", "data"),
        Output("overlay-layer", "children"),
        Output("results-table", "data"),
        Output("metrics", "children"),
        Output("map", "viewport"),
        Input("restaurant-dropdown", "value"),
        Input("radius-input", "value"),
        Input("speed-input", "value"),
        Input("show-cells", "value"),
        Input("fleet-signal", "data"),
    )
    def run_query(rid, radius, speed, show_cells, _signal):
        radius = _clamp_float(radius, 0.1, 50.0, defaults["radius"])
        speed = _clamp_float(speed, 5.0, 120.0, defaults["speed"])
        r = by_id.get(rid)
        if r is None:
            return EMPTY_GEOJSON, [], [], _message("Selecione um restaurante."), no_update

        zoom = int(max(9, min(16, round(15 - math.log2(radius)))))
        viewport = {"center": [r["lat"], r["lon"]], "zoom": zoom, "transition": "flyTo"}

        if fleet.size == 0:
            msg = _message("Ainda não há entregadores. Aguarde a geração inicial "
                           "ou clique em Gerar Entregadores.")
            return EMPTY_GEOJSON, [], [], msg, viewport

        res = fleet.query(r["lat"], r["lon"], radius, speed)
        bf_ids, bf_ms = fleet.brute_force(r["lat"], r["lon"], radius)
        inside, outside = res["inside"], res["outside"]
        identico = {x["id"] for x in inside} == bf_ids

        # ----- mapa
        feats = [{"lat": r["lat"], "lon": r["lon"], "color": COLOR_RESTAURANT, "z": 1000,
                  "popup": f"<b>{escape(r['name'])}</b><br>{escape(r['address'])}"}]
        for x in outside:
            feats.append({"lat": x["lat"], "lon": x["lon"], "color": COLOR_OUTSIDE, "z": 0,
                          "popup": (f"<b>{x['id']}</b> (fora do raio)<br>"
                                    f"{_num(x['dist_km'])} km; Geohash {x['geohash']}")})
        for x in inside:
            feats.append({"lat": x["lat"], "lon": x["lon"], "color": COLOR_INSIDE, "z": 500,
                          "popup": (f"<b>{x['id']}</b><br>{_num(x['dist_km'])} km; "
                                    f"{_num(x['eta_min'], 1)} min<br>Geohash {x['geohash']}")})
        geojson = dlx.dicts_to_geojson(feats)

        overlay = [dl.Circle(center=[r["lat"], r["lon"]], radius=radius * 1000,
                             color=COLOR_INSIDE, weight=2, fillColor=COLOR_INSIDE,
                             fillOpacity=0.06)]
        if show_cells and "cells" in show_cells:
            for gh in res["cells"]:
                la0, la1, lo0, lo1 = decode_bbox(gh)
                central = gh == res["center_cell"]
                overlay.append(dl.Rectangle(
                    bounds=[[la0, lo0], [la1, lo1]],
                    color=COLOR_RESTAURANT if central else "#64748b",
                    weight=2 if central else 1,
                    fillOpacity=0.08 if central else 0.02,
                    children=[dl.Tooltip(gh)]))

        # ----- tabela
        rows = [{"rank": i, "id": x["id"], "dist_km": round(x["dist_km"], 3),
                 "eta_min": round(x["eta_min"], 1), "geohash": x["geohash"]}
                for i, x in enumerate(inside, start=1)]

        # ----- métricas
        cards = [
            _card("Entregadores na frota", f"{fleet.size:,}".replace(",", ".")),
            _card("Células consultadas", str(len(res["cells"])),
                  f"precisão {res['precision']}; prefixo central {res['center_cell']}"),
            _card("Candidatos (Trie)", str(res["candidates"]),
                  f"{res['nodes_visited']} nós visitados"),
            _card("Dentro do raio", str(len(inside)), f"raio de {_num(radius, 1)} km",
                  accent=COLOR_INSIDE),
            _card("Descartados", str(len(outside)), "candidatos fora do raio"),
        ]
        if inside:
            dists = [x["dist_km"] for x in inside]
            etas = [x["eta_min"] for x in inside]
            cards += [
                _card("Mais próximo", f"{_num(dists[0])} km",
                      f"{_num(etas[0], 1)} min; {inside[0]['id']}"),
                _card("Distância média", f"{_num(sum(dists) / len(dists))} km",
                      f"máx. {_num(dists[-1])} km"),
                _card("Tempo médio de chegada", f"{_num(sum(etas) / len(etas), 1)} min",
                      f"a {_num(speed, 0)} km/h; fator 1,3"),
            ]
        else:
            cards.append(_card("Sem entregadores", "0", "tente aumentar o raio"))
        cards += [
            _card("Tempo da consulta", f"{_num(res['t_total_ms'], 3)} ms",
                  f"Trie {_num(res['t_trie_ms'], 3)} ms; filtro {_num(res['t_filter_ms'], 3)} ms"),
            _card("Varredura linear (ref.)", f"{_num(bf_ms, 3)} ms",
                  "idêntico" if identico else "divergente!"),
        ]
        print(f"[consulta] {r['name']} raio={radius:g}km N={fleet.size} "
              f"p={res['precision']} cand={res['candidates']} in={len(inside)} "
              f"t={res['t_total_ms']:.3f}ms (linear {bf_ms:.3f}ms)")
        return geojson, overlay, rows, cards, viewport
