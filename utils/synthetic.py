"""Gerador de dados sintéticos para a frota de entregadores.

A geração roda em segundo plano (thread). A interface não fica travada: o texto
de status da frota mostra a etapa atual (esperando a malha, gerando, projetando,
indexando), e o resultado final traz os tempos de cada etapa.
"""
import threading
import time

import numpy as np

M_PER_DEG_LAT = 111_320.0


def generate_positions(restaurants, n, sigma_m, rng, snapper=None):
    """Gera `n` posições ~ Normal(centro = restaurante, σ = sigma_m).

    - Os N entregadores são distribuídos equitativamente entre os restaurantes
      (N // R para cada um; o resto vai para restaurantes sorteados).
    - O deslocamento é gaussiano em metros, convertido para graus.
    - Se `snapper` é fornecido, cada ponto é projetado na via mais próxima.
    """
    r = len(restaurants)
    base, extra = divmod(n, r)
    counts = np.full(r, base, dtype=int)
    if extra:
        counts[rng.choice(r, size=extra, replace=False)] += 1

    c_lat = np.repeat(np.array([x["lat"] for x in restaurants]), counts)
    c_lon = np.repeat(np.array([x["lon"] for x in restaurants]), counts)

    dy = rng.normal(0.0, sigma_m, size=n)
    dx = rng.normal(0.0, sigma_m, size=n)
    lats = c_lat + dy / M_PER_DEG_LAT
    lons = c_lon + dx / (M_PER_DEG_LAT * np.cos(np.radians(c_lat)))

    if snapper is not None:
        lats, lons = snapper.snap(lats, lons)
    return lats.tolist(), lons.tolist()


def _fmt(x):
    return f"{x:,}".replace(",", ".")


def start_fleet_job(restaurants, fleet, snapper, n, sigma_m):
    """Inicia a geração em segundo plano. False se já houver uma em andamento."""
    with fleet.lock:
        if fleet.busy:
            return False
        fleet.busy = True
    threading.Thread(target=_job, args=(restaurants, fleet, snapper, n, sigma_m),
                     daemon=True).start()
    return True


def _job(restaurants, fleet, snapper, n, sigma_m):
    try:
        snapped, warn = False, ""
        t_wait = 0.0
        if snapper is not None:
            t_a = time.perf_counter()
            while not snapper.finished:
                fleet.set_status(f"Aguardando a malha viária; {snapper.stage}")
                snapper.wait_ready(0.5)
            t_wait = time.perf_counter() - t_a
            snapped = snapper.ready
            if not snapped:
                warn = f" (sem correção viária: {snapper.error})"

        fleet.set_status(f"Gerando {_fmt(n)} posições (dispersão {sigma_m:g} m)…")
        rng = np.random.default_rng()
        t_b = time.perf_counter()
        if snapped:
            fleet.set_status(f"Projetando {_fmt(n)} entregadores nas vias…")
        lats, lons = generate_positions(restaurants, n, sigma_m, rng,
                                        snapper if snapped else None)
        t_gen = time.perf_counter() - t_b

        fleet.set_status("Indexando na Trie…")
        fleet.rebuild(lats, lons)
        fleet.snapped = snapped
        fleet.sigma_m = sigma_m
        nodes = fleet.trie.node_count()
        fleet.info = (
            f"{_fmt(n)} entregadores (dispersão {sigma_m:g} m"
            f"{', projetados nas vias' if snapped else ''}); "
            f"espera pela malha {t_wait:.1f} s; geração + projeção {t_gen:.2f} s; "
            f"Trie {fleet.build_ms:.1f} ms ({_fmt(nodes)} nós)" + warn
        )
        fleet.set_status(fleet.info)
        print(f"[frota] {fleet.info}", flush=True)
    except Exception as exc:  # noqa: BLE001
        fleet.set_status(f"Falha ao gerar entregadores: {exc}")
        print(f"[frota] ERRO: {exc}", flush=True)
    finally:
        fleet.busy = False
