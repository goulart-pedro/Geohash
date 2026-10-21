"""Codificação Geohash (Base32) implementada do zero.

O Geohash é obtido por bissecções sucessivas dos intervalos de longitude e
latitude, intercalando os bits (o primeiro bit é sempre de longitude).
A cada 5 bits gera-se um caractere do alfabeto Base32 do Geohash.
"""
import math

BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
_DECODE = {c: i for i, c in enumerate(BASE32)}

MAX_PRECISION = 8           # limite de níveis exigido no enunciado
M_PER_DEG_LAT = 110_574.0   # menor valor ao longo do globo (conservador)
M_PER_DEG_LON_EQ = 111_320.0

# deslocamentos (linha, coluna) das 8 células vizinhas
DIRECTIONS = {
    "n": (1, 0), "ne": (1, 1), "e": (0, 1), "se": (-1, 1),
    "s": (-1, 0), "sw": (-1, -1), "w": (0, -1), "nw": (1, -1),
}


def encode(lat, lon, precision=MAX_PRECISION):
    """Converte (lat, lon) em Geohash com `precision` caracteres."""
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise ValueError(f"Coordenada inválida: ({lat}, {lon})")
    lat_lo, lat_hi = -90.0, 90.0
    lon_lo, lon_hi = -180.0, 180.0
    chars = []
    bits = 0
    nbits = 0
    use_lon = True
    while len(chars) < precision:
        if use_lon:
            mid = (lon_lo + lon_hi) / 2.0
            if lon >= mid:
                bits = (bits << 1) | 1
                lon_lo = mid
            else:
                bits <<= 1
                lon_hi = mid
        else:
            mid = (lat_lo + lat_hi) / 2.0
            if lat >= mid:
                bits = (bits << 1) | 1
                lat_lo = mid
            else:
                bits <<= 1
                lat_hi = mid
        use_lon = not use_lon
        nbits += 1
        if nbits == 5:
            chars.append(BASE32[bits])
            bits = 0
            nbits = 0
    return "".join(chars)


def decode_bbox(geohash):
    """Retorna (lat_min, lat_max, lon_min, lon_max) da célula."""
    lat_lo, lat_hi = -90.0, 90.0
    lon_lo, lon_hi = -180.0, 180.0
    use_lon = True
    for ch in geohash:
        val = _DECODE[ch]
        for shift in (4, 3, 2, 1, 0):
            bit = (val >> shift) & 1
            if use_lon:
                mid = (lon_lo + lon_hi) / 2.0
                if bit:
                    lon_lo = mid
                else:
                    lon_hi = mid
            else:
                mid = (lat_lo + lat_hi) / 2.0
                if bit:
                    lat_lo = mid
                else:
                    lat_hi = mid
            use_lon = not use_lon
    return lat_lo, lat_hi, lon_lo, lon_hi


def decode(geohash):
    """Centro da célula: (lat, lon)."""
    lat_lo, lat_hi, lon_lo, lon_hi = decode_bbox(geohash)
    return (lat_lo + lat_hi) / 2.0, (lon_lo + lon_hi) / 2.0


def cell_size_deg(precision):
    """(altura, largura) em graus de uma célula com `precision` caracteres."""
    total = 5 * precision
    lon_bits = (total + 1) // 2
    lat_bits = total // 2
    return 180.0 / (1 << lat_bits), 360.0 / (1 << lon_bits)


def cell_size_m(precision, lat):
    """(altura, largura) aproximadas, em metros, na latitude `lat`."""
    dlat, dlon = cell_size_deg(precision)
    return (dlat * M_PER_DEG_LAT,
            dlon * M_PER_DEG_LON_EQ * math.cos(math.radians(lat)))


def neighbors(geohash):
    """As (até) 8 células adjacentes, calculadas pelo centro ± tamanho da célula."""
    lat_lo, lat_hi, lon_lo, lon_hi = decode_bbox(geohash)
    clat = (lat_lo + lat_hi) / 2.0
    clon = (lon_lo + lon_hi) / 2.0
    dlat = lat_hi - lat_lo
    dlon = lon_hi - lon_lo
    p = len(geohash)
    result = {}
    for name, (di, dj) in DIRECTIONS.items():
        nlat = clat + di * dlat
        if nlat < -90.0 or nlat > 90.0:
            continue                       # além dos polos
        nlon = clon + dj * dlon
        nlon = ((nlon + 180.0) % 360.0) - 180.0   # wrap na longitude
        result[name] = encode(nlat, nlon, p)
    return result


def adjacent_cells(geohash):
    """Célula central + vizinhas, sem repetições (a central vem primeiro)."""
    cells = [geohash]
    for gh in neighbors(geohash).values():
        if gh not in cells:
            cells.append(gh)
    return cells


def precision_for_radius(radius_km, lat, max_precision=MAX_PRECISION):
    """Maior precisão cuja célula é >= raio (com 2% de folga).

    Com células de lado >= raio, a vizinhança 3x3 do restaurante cobre
    inteiramente o círculo de busca, o que elimina o problema de borda.
    """
    r_m = radius_km * 1000.0 * 1.02
    for p in range(max_precision, 0, -1):
        h, w = cell_size_m(p, lat)
        if min(h, w) >= r_m:
            return p
    return 1
