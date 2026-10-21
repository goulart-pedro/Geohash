"""Malha viária de Belo Horizonte (OpenStreetMap via osmnx).

Carregamento em segundo plano, em etapas registradas e cronometradas (o status
aparece na interface e no terminal):
  1. cache local (grafo já projetado, em pickle): leitura de alguns segundos;
  2. sem cache: download do OSM (lento), projeção e gravação do cache.

Depois de carregada, a projeção dos pontos na via mais próxima é vetorizada:
um STRtree (shapely) sobre as geometrias das arestas dá a aresta mais próxima de
cada ponto de uma vez, e a interpolação projeta o ponto sobre ela. Não há mais
conversão do grafo a cada chamada nem laço Python por ponto.
"""
import os
import pickle
import threading
import time

import numpy as np


class RoadSnapper:
    PLACE = "Belo Horizonte, Minas Gerais, Brazil"

    def __init__(self, cache_dir="cache"):
        self.cache_path = os.path.join(cache_dir, "bh_drive_utm.pkl")
        self.G = None
        self.error = None
        self.stage = "aguardando início"
        self.load_seconds = None
        self._ready = threading.Event()
        self._lock = threading.Lock()
        self._started = False
        self._t0 = time.perf_counter()

    # ------------------------------------------------------------ estado
    @property
    def ready(self):
        """Malha carregada e utilizável."""
        return self.G is not None

    @property
    def finished(self):
        """Carregamento terminou (com sucesso ou com erro)."""
        return self._ready.is_set()

    def _step(self, msg):
        self.stage = msg
        print(f"[malha +{time.perf_counter() - self._t0:6.1f}s] {msg}", flush=True)

    # ------------------------------------------------------- carregamento
    def start(self):
        """Dispara o carregamento em background (só na primeira chamada)."""
        with self._lock:
            if self._started:
                return
            self._started = True
        self._t0 = time.perf_counter()
        threading.Thread(target=self._load, daemon=True).start()

    def wait_ready(self, timeout=None):
        """Espera até `timeout` segundos. Retorna True se a malha está pronta."""
        self.start()
        self._ready.wait(timeout)
        return self.ready

    def ensure_loaded(self):
        """Bloqueia até a malha estar pronta; levanta erro se o carregamento falhou."""
        self.wait_ready()
        if self.G is None:
            raise RuntimeError(self.error or "malha não carregada")

    def _load(self):
        try:
            self._load_graph()
            self.load_seconds = time.perf_counter() - self._t0
            self._step(f"malha pronta em {self.load_seconds:.1f} s")
        except Exception as exc:  # noqa: BLE001
            self.error = f"{exc.__class__.__name__}: {exc}"
            self._step(f"ERRO ao carregar a malha: {self.error}")
        finally:
            self._ready.set()

    def _load_graph(self):
        import osmnx as ox

        if os.path.exists(self.cache_path):
            self._step(f"lendo cache {self.cache_path}")
            with open(self.cache_path, "rb") as f:
                G = pickle.load(f)
        else:
            self._step(f"baixando do OpenStreetMap: {self.PLACE} "
                       "(1ª execução; pode levar vários minutos)")
            G = ox.project_graph(ox.graph_from_place(self.PLACE, network_type="drive"))
            self._step("gravando cache")
            os.makedirs(os.path.dirname(self.cache_path) or ".", exist_ok=True)
            with open(self.cache_path, "wb") as f:
                pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)
        self._step(f"indexando {G.number_of_edges():,} arestas".replace(",", "."))
        self._index(G)

    def _index(self, G):
        """Monta o índice espacial a partir de um grafo já projetado (UTM)."""
        import shapely
        from pyproj import Transformer
        from shapely.geometry import LineString

        nodes = G.nodes
        geoms = []
        for u, v, k, data in G.edges(keys=True, data=True):
            geom = data.get("geometry")
            if geom is None:
                geom = LineString([(nodes[u]["x"], nodes[u]["y"]),
                                   (nodes[v]["x"], nodes[v]["y"])])
            geoms.append(geom)
        arr = np.empty(len(geoms), dtype=object)
        for i, g in enumerate(geoms):
            arr[i] = g
        self._geoms_arr = arr
        self._tree = shapely.STRtree(arr)

        crs = G.graph["crs"]
        self._to_proj = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        self._to_ll = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
        self.G = G                       # por último: `ready` só vale com o índice pronto

    # ----------------------------------------------------------- projeção
    def _snap_proj(self, xs, ys):
        """Projeta pontos (coordenadas UTM) sobre a aresta mais próxima. Vetorizado."""
        import shapely

        pts = shapely.points(np.asarray(xs, dtype=float), np.asarray(ys, dtype=float))
        inp, tr = self._tree.query_nearest(pts)     # pares (ponto, aresta)
        idx = np.full(len(pts), -1, dtype=np.int64)
        idx[inp[::-1]] = tr[::-1]                   # fica a primeira aresta de cada ponto
        geoms = self._geoms_arr[idx]
        d = shapely.line_locate_point(geoms, pts)   # distância ao longo da aresta
        out = shapely.line_interpolate_point(geoms, d)
        return shapely.get_x(out), shapely.get_y(out)

    def snap(self, lats, lons):
        """Retorna (lats, lons) corrigidos para pontos sobre as vias."""
        self.ensure_loaded()
        xs, ys = self._to_proj.transform(np.asarray(lons, dtype=float),
                                         np.asarray(lats, dtype=float))
        sx, sy = self._snap_proj(xs, ys)
        new_lons, new_lats = self._to_ll.transform(sx, sy)
        return np.asarray(new_lats), np.asarray(new_lons)
