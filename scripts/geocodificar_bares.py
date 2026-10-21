"""Geocodifica o bares.csv (Nominatim/OSM) e gera data/restaurantes.csv.

O Nominatim limita a 1 requisição/s, então o script:
  * sorteia os estabelecimentos (semente fixa) e para ao atingir --limite
    endereços geocodificados com sucesso;
  * guarda um cache em disco (retomável: pode ser interrompido com Ctrl+C);
  * descarta resultados fora da caixa geográfica de Belo Horizonte.

Uso:
    python scripts/geocodificar_bares.py --limite 200
"""
import argparse
import csv
import json
import os
import random
import sys

from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim

BH_BBOX = (-20.06, -19.76, -44.07, -43.85)   # lat_min, lat_max, lon_min, lon_max

TIPOS = {
    "AVE": "Avenida", "AV": "Avenida", "RUA": "Rua", "R": "Rua", "ALA": "Alameda",
    "PCA": "Praça", "PRA": "Praça", "TRV": "Travessa", "BEC": "Beco",
    "ROD": "Rodovia", "EST": "Estrada", "VIA": "Via", "VLA": "Viela",
    "LGO": "Largo", "CAM": "Caminho", "VDT": "Viaduto", "GAL": "Galeria",
    "PQE": "Parque", "ROT": "Rotatória", "BLV": "Boulevard",
}
MINUSCULAS = {"De", "Da", "Do", "Das", "Dos", "E", "Di", "Du"}


def bonito(texto):
    palavras = texto.strip().title().split()
    return " ".join(p.lower() if i > 0 and p in MINUSCULAS else p
                    for i, p in enumerate(palavras))


def ler_csv(caminho):
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(caminho, "r", encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"Não foi possível ler {caminho}")


def montar(row):
    tipo = TIPOS.get(row["DESC_LOGRADOURO"].strip().upper(),
                     bonito(row["DESC_LOGRADOURO"]))
    rua = bonito(row["NOME_LOGRADOURO"])
    numero = row["NUMERO_IMOVEL"].strip()
    if numero.upper() in ("", "0", "S/N", "SN", "SEM NUMERO"):
        numero = ""
    bairro = bonito(row["NOME_BAIRRO"])
    nome = bonito(row["NOME_FANTASIA"].strip() or row["NOME"])
    endereco = f"{tipo} {rua}" + (f", {numero}" if numero else "") + f", {bairro}"
    return nome, tipo, rua, numero, bairro, endereco


def dentro_de_bh(lat, lon):
    return BH_BBOX[0] <= lat <= BH_BBOX[1] and BH_BBOX[2] <= lon <= BH_BBOX[3]


def consultas(tipo, rua, numero, bairro):
    cidade = {"city": "Belo Horizonte", "state": "Minas Gerais", "country": "Brazil"}
    if numero:
        yield {"street": f"{numero} {tipo} {rua}", **cidade}
    yield (f"{tipo} {rua}, {numero}, {bairro}, Belo Horizonte, MG, Brasil"
           if numero else f"{tipo} {rua}, {bairro}, Belo Horizonte, MG, Brasil")
    yield f"{tipo} {rua}, Belo Horizonte, MG, Brasil"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entrada", default="data/bares.csv")
    ap.add_argument("--saida", default="data/restaurantes.csv")
    ap.add_argument("--cache", default="data/cache_geocodificacao.json")
    ap.add_argument("--limite", type=int, default=200,
                    help="nº de estabelecimentos geocodificados (0 = todos)")
    ap.add_argument("--semente", type=int, default=42)
    args = ap.parse_args()

    if not os.path.exists(args.entrada):
        sys.exit(f"Arquivo não encontrado: {args.entrada}")

    rows = ler_csv(args.entrada)
    random.Random(args.semente).shuffle(rows)

    cache = {}
    if os.path.exists(args.cache):
        with open(args.cache, encoding="utf-8") as f:
            cache = json.load(f)

    geoloc = Nominatim(user_agent="tp1-alg2-geohash-ufmg", timeout=10)
    geocode = RateLimiter(geoloc.geocode, min_delay_seconds=1.1, max_retries=2,
                          error_wait_seconds=5.0, swallow_exceptions=True,
                          return_value_on_exception=None)

    saida = []
    vistos = set()

    def salvar():
        with open(args.saida, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "nome", "endereco", "lat", "lon"])
            w.writerows(saida)
        with open(args.cache, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)

    tentativas = 0
    try:
        for row in rows:
            if args.limite and len(saida) >= args.limite:
                break
            rid = row["_id"].strip()
            nome, tipo, rua, numero, bairro, endereco = montar(row)

            if rid not in cache:
                cache[rid] = None
                for q in consultas(tipo, rua, numero, bairro):
                    loc = geocode(q)
                    if loc and dentro_de_bh(loc.latitude, loc.longitude):
                        cache[rid] = {"lat": loc.latitude, "lon": loc.longitude}
                        break
                tentativas += 1
                if tentativas % 10 == 0:
                    salvar()
            res = cache[rid]
            if res is None:
                continue
            chave = (round(res["lat"], 6), round(res["lon"], 6))
            if chave in vistos:
                continue
            vistos.add(chave)
            saida.append([rid, nome, endereco, f"{res['lat']:.7f}", f"{res['lon']:.7f}"])
            print(f"[{len(saida):4d}] {nome}: {endereco}")
    except KeyboardInterrupt:
        print("\nInterrompido; salvando o que foi obtido…")
    finally:
        salvar()
    print(f"\n{len(saida)} estabelecimentos salvos em {args.saida}")


if __name__ == "__main__":
    main()
