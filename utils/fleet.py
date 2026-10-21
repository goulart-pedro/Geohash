"""Frota de entregadores: armazenamento na Trie e consulta geoespacial híbrida."""
import threading
from time import perf_counter

from .geohash import (MAX_PRECISION, adjacent_cells, encode,
                      precision_for_radius)
from .geo import eta_minutes, haversine_km
from .trie import CompactTrie


class Fleet:
    def __init__(self):
        self._state = ({}, CompactTrie())   # (couriers, trie) trocados atomicamente
        self.version = 0
        self.info = ""
        self.status_text = "Aguardando início…"
        self.busy = False
        self.lock = threading.Lock()
        self.boot_error = None
        self.build_ms = 0.0
        self.snapped = False
        self.sigma_m = None

    def set_status(self, text):
        self.status_text = text

    @property
    def couriers(self):
        return self._state[0]

    @property
    def trie(self):
        return self._state[1]

    @property
    def size(self):
        return len(self._state[0])

    def rebuild(self, lats, lons):
        """Descarta tudo o que existia e indexa as novas posições."""
        t0 = perf_counter()
        couriers = {}
        trie = CompactTrie()
        for i, (la, lo) in enumerate(zip(lats, lons), start=1):
            la, lo = float(la), float(lo)
            gh = encode(la, lo, MAX_PRECISION)
            cid = f"E{i:05d}"
            couriers[cid] = (la, lo, gh)
            trie.insert(gh, cid)
        self.build_ms = (perf_counter() - t0) * 1000.0
        self._state = (couriers, trie)
        self.version += 1

    def query(self, lat, lon, radius_km, speed_kmh):
        """Etapa 1: Geohash + 9 células na Trie. Etapa 2: filtro por distância."""
        couriers, trie = self._state
        t0 = perf_counter()
        precision = precision_for_radius(radius_km, lat)
        center = encode(lat, lon, precision)
        cells = adjacent_cells(center)
        ids = []
        visited = 0
        for prefix in cells:
            ids.extend(trie.search_prefix(prefix))
            visited += trie.last_nodes_visited
        t1 = perf_counter()

        inside, outside = [], []
        for cid in ids:
            clat, clon, gh = couriers[cid]
            d = haversine_km(lat, lon, clat, clon)
            rec = {"id": cid, "lat": clat, "lon": clon, "geohash": gh,
                   "dist_km": d, "eta_min": eta_minutes(d, speed_kmh)}
            (inside if d <= radius_km else outside).append(rec)
        inside.sort(key=lambda r: r["dist_km"])
        t2 = perf_counter()

        return {
            "precision": precision, "center_cell": center, "cells": cells,
            "candidates": len(ids), "inside": inside, "outside": outside,
            "nodes_visited": visited,
            "t_trie_ms": (t1 - t0) * 1000.0,
            "t_filter_ms": (t2 - t1) * 1000.0,
            "t_total_ms": (t2 - t0) * 1000.0,
        }

    def brute_force(self, lat, lon, radius_km):
        """Varredura linear de referência (valida o resultado e dá o baseline)."""
        couriers = self._state[0]
        t0 = perf_counter()
        ids = {cid for cid, (clat, clon, _) in couriers.items()
               if haversine_km(lat, lon, clat, clon) <= radius_km}
        return ids, (perf_counter() - t0) * 1000.0
