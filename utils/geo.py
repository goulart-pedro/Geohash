"""Funções geométricas auxiliares (distância e tempo estimado de chegada)."""
import math

EARTH_RADIUS_KM = 6371.0088
DETOUR_FACTOR = 1.3     # fator de circuidade: rua real ~30% maior que a reta


def haversine_km(lat1, lon1, lat2, lon2):
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def eta_minutes(dist_km, speed_kmh):
    """Tempo estimado (min) = distância * fator de circuidade / velocidade média."""
    if speed_kmh <= 0:
        return float("inf")
    return dist_km * DETOUR_FACTOR / speed_kmh * 60.0
