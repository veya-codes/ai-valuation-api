import hashlib
from math import sin

def normalize_address(addr: str) -> str:
    """
    Minimal normalization so cache keys & seeds are stable:
    - trim whitespace
    - lowercase
    - collapse multiple spaces
    """
    return " ".join(addr.strip().lower().split())

def fnv1a_32(s: str) -> int:
    """Deterministic, fast hash for seed generation."""
    h = 0x811c9dc5
    for c in s.encode("utf-8"):
        h ^= c
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h

def seeded_rand(seed: int, n: int = 1) -> list[float]:
    """
    Stateless pseudo-random generator (Mulberry32-like) so
    same seed → same outputs without storing PRNG state.
    """
    out = []
    t = (seed + 0x6D2B79F5) & 0xFFFFFFFF
    for _ in range(n):
        t = (t ^ (t >> 15)) * (t | 1) & 0xFFFFFFFF
        t ^= t + ((t ^ (t >> 7)) * (t | 61) & 0xFFFFFFFF)
        r = ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0
        out.append(r)
    return out

def money_band(base: int, seed: int) -> tuple[int, int]:
    """Compute +/- spread around base price using seed for variety."""
    spread = 0.05 + seeded_rand(seed+1, 1)[0] * 0.07  # 5–12%
    low = int(round(base * (1 - spread)))
    high = int(round(base * (1 + spread)))
    return low, high

def sparkline(seed: int) -> list[int]:
    """Generate 12 ‘index’ points for charts. Visual only."""
    pts = []
    for i in range(12):
        v = 50 + sin((i+1)*0.6 + (seed % 10)) * 10 + seeded_rand(seed+i, 1)[0]*14
        v = max(0, min(100, v))
        pts.append(int(round(v)))
    return pts

def weak_etag(payload_bytes: bytes) -> str:
    """Weak ETag for client-side conditional requests."""
    h = hashlib.sha256(payload_bytes).hexdigest()[:24]
    return f'W/"{h}"'
