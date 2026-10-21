"""Testes da projeção na via, sem rede: grafo sintético em UTM (zona 23S, EPSG:32723).

Execução (na raiz do projeto):  python -m unittest tests.test_malha -v
"""
import tempfile
import unittest

import networkx as nx
import numpy as np

from utils.road_snap import RoadSnapper


def _grafo():
    """Dois trechos em L: horizontal (y = 7800000) e vertical (x = 600100)."""
    G = nx.MultiDiGraph()
    G.graph["crs"] = "EPSG:32723"
    G.add_node(1, x=600000.0, y=7800000.0)
    G.add_node(2, x=600100.0, y=7800000.0)
    G.add_node(3, x=600100.0, y=7800100.0)
    for u, v in ((1, 2), (2, 1), (2, 3), (3, 2)):
        G.add_edge(u, v, 0, length=100.0)
    return G


class TestProjecaoNaVia(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self.snap = RoadSnapper(cache_dir=self._tmp)
        self.snap._index(_grafo())

    def _proj(self, x, y):
        sx, sy = self.snap._snap_proj([x], [y])
        return float(sx[0]), float(sy[0])

    def test_ponto_sobre_trecho_horizontal(self):
        x, y = self._proj(600030.0, 7800005.0)
        self.assertAlmostEqual(x, 600030.0, places=6)
        self.assertAlmostEqual(y, 7800000.0, places=6)

    def test_ponto_sobre_trecho_vertical(self):
        x, y = self._proj(600095.0, 7800050.0)
        self.assertAlmostEqual(x, 600100.0, places=6)
        self.assertAlmostEqual(y, 7800050.0, places=6)

    def test_ponto_no_fim_da_via(self):
        x, y = self._proj(600110.0, 7800090.0)
        self.assertAlmostEqual(x, 600100.0, places=6)
        self.assertAlmostEqual(y, 7800090.0, places=6)

    def test_lote_vetorizado_fica_sobre_as_vias(self):
        rng = np.random.default_rng(0)
        xs = rng.uniform(599950, 600150, 5000)
        ys = rng.uniform(7799950, 7800150, 5000)
        sx, sy = self.snap._snap_proj(xs, ys)
        on_h = np.isclose(sy, 7800000.0, atol=1e-6) & (sx >= 600000 - 1e-6) & (sx <= 600100 + 1e-6)
        on_v = np.isclose(sx, 600100.0, atol=1e-6) & (sy >= 7800000 - 1e-6) & (sy <= 7800100 + 1e-6)
        self.assertTrue(np.all(on_h | on_v))

    def test_status_sem_cache_e_erro_nao_bloqueia(self):
        s = RoadSnapper(cache_dir=self._tmp)
        self.assertFalse(s.ready)
        self.assertFalse(s.finished)


if __name__ == "__main__":
    unittest.main()
