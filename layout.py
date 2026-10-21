from dash import dash_table, dcc, html

from components.map import build_map


def _field(label, component, extra_class=""):
    return html.Div([html.Label(label, className="field-label"), component],
                    className=f"field {extra_class}".strip())


def _legend_item(color, text):
    return html.Span([html.Span(className="dot", style={"backgroundColor": color}), text],
                     className="legend-item")


def get_layout(restaurants, restaurants_geojson, center, defaults):
    options = [
        {"label": f"{r['name']} ({r['address']})", "value": r["id"]}
        for r in sorted(restaurants, key=lambda r: r["name"].lower())
    ]
    default_rid = options[0]["value"] if options else None

    controles = html.Div([
        html.Div([
            _field("Restaurante (nome ou endereço)",
                   dcc.Dropdown(id="restaurant-dropdown", options=options,
                                value=default_rid, clearable=False, searchable=True,
                                placeholder="Digite o nome ou o endereço…"),
                   "field-wide"),
        ], className="controls-row"),
        html.Div([
            _field("Raio de atendimento (km)",
                   dcc.Input(id="radius-input", type="number", value=defaults["radius"],
                             min=0.1, max=50, step=0.1, debounce=True, className="input")),
            _field("Velocidade média (km/h)",
                   dcc.Input(id="speed-input", type="number", value=defaults["speed"],
                             min=5, max=120, step=1, debounce=True, className="input")),
            _field("Nº de entregadores (N)",
                   dcc.Input(id="n-input", type="number", value=defaults["n"],
                             min=1, max=defaults["max_n"], step=1, debounce=True,
                             className="input")),
            _field("Dispersão (metros)",
                   dcc.Input(id="sigma-input", type="number", value=defaults["sigma"],
                             min=20, max=5000, step=10, debounce=True, className="input")),
            html.Div(html.Button("Gerar Entregadores", id="btn-generate",
                                 n_clicks=0, className="btn btn-primary"),
                     className="field field-button"),
        ], className="controls-row"),
        html.Div([
            dcc.Checklist(id="show-cells",
                          options=[{"label": " Mostrar células Geohash consultadas",
                                    "value": "cells"}],
                          value=["cells"], className="checklist"),
            dcc.Loading(html.Div(id="status", className="status",
                                 children="Carregando a malha viária…"),
                        type="dot"),
        ], className="controls-row controls-footer"),
    ], className="card controls")

    legenda = html.Div([
        _legend_item("#3498db", "Restaurante"),
        _legend_item("#e53935", "Entregador dentro do raio"),
        _legend_item("#9e9e9e", "Candidato descartado (fora do raio)"),
        html.Span("Dica: clique em um restaurante no mapa para selecioná-lo.",
                  className="legend-hint"),
    ], className="legend")

    tabela = dash_table.DataTable(
        id="results-table",
        columns=[
            {"name": "#", "id": "rank"},
            {"name": "Entregador", "id": "id"},
            {"name": "Distância (km)", "id": "dist_km", "type": "numeric"},
            {"name": "Tempo estimado (min)", "id": "eta_min", "type": "numeric"},
            {"name": "Geohash", "id": "geohash"},
        ],
        data=[],
        page_size=10,
        sort_action="native",
        export_format="csv",
        style_table={"overflowX": "auto"},
        style_header={"backgroundColor": "#2c3e50", "color": "white",
                      "fontWeight": "600", "textAlign": "center", "border": "none"},
        style_cell={"padding": "10px", "textAlign": "center", "border": "none",
                    "fontFamily": "inherit", "fontSize": "14px"},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"}],
    )

    return html.Div([
        dcc.Store(id="fleet-signal", data=None),
        dcc.Interval(id="poll", interval=1000, n_intervals=0),
        html.Header([
            html.H1("Entregadores", className="app-title"),
        ], className="app-header"),
        html.Div([
            controles,
            legenda,
            build_map(restaurants_geojson, center),
            html.H2("Resumo da consulta", className="section-title"),
            html.Div(id="metrics", className="metrics-grid"),
            html.H2("Entregadores dentro do raio", className="section-title"),
            html.Div(tabela, className="card table-wrapper"),
        ], className="content-wrapper"),
    ], className="main-container")
