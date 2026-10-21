"""Testes das estruturas centrais (somente biblioteca padrão).

Execução (na raiz do projeto):  python -m unittest tests.test_estruturas -v
"""
import random
import unittest

from utils.fleet import Fleet
from utils.geohash import (adjacent_cells, decode_bbox, encode, neighbors,
                           precision_for_radius)
from utils.trie import CompactTrie


class TestGeohash(unittest.TestCase):
    def test_valores_conhecidos(self):
        self.assertEqual(encode(57.64911, 10.40744, 11), "u4pruydqqvj")
        self.assertEqual(encode(42.6, -5.6, 5), "ezs42")

    def test_bbox_contem_ponto(self):
        rnd = random.Random(1)
        for _ in range(500):
            lat, lon = rnd.uniform(-89, 89), rnd.uniform(-179, 179)
            for p in (1, 4, 8):
                la0, la1, lo0, lo1 = decode_bbox(encode(lat, lon, p))
                self.assertTrue(la0 <= lat <= la1 and lo0 <= lon <= lo1)

    def test_vizinhos(self):
        gh = encode(-19.9102, -43.9266, 6)
        viz = neighbors(gh)
        self.assertEqual(len(viz), 8)
        self.assertEqual(len(adjacent_cells(gh)), 9)
        la0, la1, lo0, lo1 = decode_bbox(gh)
        for nb in viz.values():
            self.assertNotEqual(nb, gh)
            nla0, nla1, nlo0, nlo1 = decode_bbox(nb)
            # compartilha borda ou canto com a célula original
            self.assertTrue(abs(nla0 - la0) <= (la1 - la0) * 1.0001)
            self.assertTrue(abs(nlo0 - lo0) <= (lo1 - lo0) * 1.0001)

    def test_precisao_por_raio(self):
        self.assertLessEqual(precision_for_radius(2.0, -19.9), 5)
        self.assertGreaterEqual(precision_for_radius(0.5, -19.9), 6)


class TestTrie(unittest.TestCase):
    def test_busca_por_prefixo_igual_a_forca_bruta(self):
        rnd = random.Random(7)
        chaves = [encode(-19.9 + rnd.gauss(0, .05), -43.95 + rnd.gauss(0, .05), 8)
                  for _ in range(3000)]
        trie = CompactTrie()
        for i, k in enumerate(chaves):
            trie.insert(k, i)
        self.assertEqual(len(trie), 3000)
        for _ in range(300):
            pref = rnd.choice(chaves)[:rnd.randint(0, 8)]
            esperado = sorted(i for i, k in enumerate(chaves) if k.startswith(pref))
            self.assertEqual(sorted(trie.search_prefix(pref)), esperado)
        self.assertEqual(trie.search_prefix("zzzzzzzz"), [])

    def test_chaves_repetidas(self):
        t = CompactTrie()
        t.insert("7n8r", "a")
        t.insert("7n8r", "b")
        t.insert("7n8", "c")
        self.assertEqual(sorted(t.search_prefix("7n")), ["a", "b", "c"])
        self.assertEqual(sorted(t.search_prefix("7n8r")), ["a", "b"])


class TestConsulta(unittest.TestCase):
    def test_consulta_igual_a_varredura_linear_inclusive_nas_bordas(self):
        rnd = random.Random(3)
        lats = [-19.92 + rnd.uniform(-.04, .04) for _ in range(8000)]
        lons = [-43.94 + rnd.uniform(-.04, .04) for _ in range(8000)]
        f = Fleet()
        f.rebuild(lats, lons)
        for _ in range(150):
            lat = -19.92 + rnd.uniform(-.03, .03)
            lon = -43.94 + rnd.uniform(-.03, .03)
            raio = rnd.choice([0.05, 0.3, 1.0, 2.0, 4.0])
            res = f.query(lat, lon, raio, 25.0)
            bf, _ = f.brute_force(lat, lon, raio)
            self.assertEqual({r["id"] for r in res["inside"]}, bf)


if __name__ == "__main__":
    unittest.main()
