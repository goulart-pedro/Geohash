# TP1 – Indexação Geoespacial e Geometria Computacional Híbrida

Motor de busca e monitoramento de entregadores em Belo Horizonte.
A consulta combina **Geohash (8 níveis) + Trie compacta** (filtro grosseiro, O(m + k)),
cobertura das **8 células vizinhas** (problema de borda) e **filtragem geométrica**
por distância (haversine) dentro de um raio configurável.

## Execução local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1) Coloque o bares.csv em data/ e geocodifique (uma vez; ~1 req/s, retomável)
python scripts/geocodificar_bares.py --limite 200

# 2) Suba a aplicação (a malha viária é baixada na 1ª execução e fica em cache/)
python main.py            # http://localhost:8050
```

### Docker

```bash
docker build -t tp1-geohash .
docker run -p 8050:8050 tp1-geohash
```

> O `data/restaurantes.csv` gerado no passo 1 deve estar no repositório
> (o Dockerfile o copia).

## Estrutura

```
main.py                 # inicialização, frota inicial em background
layout.py               # interface (Dash)
callbacks.py            # geração da frota, consulta, mapa, tabela, métricas
components/map.py       # mapa dash-leaflet (pinos SVG, clusters)
utils/geohash.py        # encode/decode Base32, vizinhos, escolha da precisão
utils/trie.py           # Trie compacta (radix) — implementação própria
utils/fleet.py          # frota + consulta híbrida (Trie → filtro) + varredura linear
utils/synthetic.py      # gerador normal centrado nos restaurantes
utils/road_snap.py      # projeção na via mais próxima (osmnx)
scripts/                # geocodificação, download da malha, benchmark
tests/                  # testes unitários
RELATORIO.md            # modelo do relatório
```

## Decisões de projeto (resumo)

* **Geohash**: bissecção de intervalos com bits intercalados (lon primeiro), 5 bits por
  caractere Base32, 8 caracteres.
* **Trie compacta**: nós com rótulo de aresta; divisão de arestas na inserção; valores
  (IDs) guardados no nó terminal (vários entregadores podem compartilhar um Geohash).
* **Borda**: a precisão do prefixo é a maior cuja célula tem lado ≥ raio; assim a
  vizinhança 3×3 do restaurante cobre todo o círculo. Ex.: raio 2 km → precisão 5.
* **Filtragem**: haversine ≤ raio; pinos vermelhos (dentro) e cinza (descartados).
* **Tempo de chegada**: distância × 1,3 (circuidade) ÷ velocidade média (parâmetro).
* **Dados sintéticos**: N dividido igualmente entre os restaurantes; deslocamento
  N(0, σ) em metros; depois cada ponto é projetado sobre a geometria da aresta
  mais próxima do grafo viário (osmnx, rede `drive`, grafo projetado em UTM).
* **Verificação**: cada consulta é comparada com uma varredura linear (exibida na UI).

## Testes e benchmark

```bash
python -m unittest tests.test_estruturas -v
python scripts/benchmark.py --tamanhos 1000 10000 50000
```
