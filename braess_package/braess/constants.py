"""
BPR (Bureau of Public Roads) link cost function and road-class lookup tables.

This is the only file that defines what "congestion" means numerically —
every other module imports from here rather than redefining constants, so
changing the congestion model (e.g. recalibrating alpha/beta for a specific
city, or adding a new highway class) only requires editing this one file.
"""
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# BPR Link Cost Function  t(x) = t0 * (1 + alpha*(x/C)^beta)
# Standard transportation-engineering defaults (US Bureau of Public Roads, 1964)
# ─────────────────────────────────────────────────────────────────────────────
BPR_ALPHA = 0.15
BPR_BETA = 4.0


def bpr_cost_vec(flow, fft, cap):
    """Vectorised BPR travel-time cost. Accepts scalars or numpy arrays."""
    flow = np.asarray(flow, dtype=float)
    return fft * (1.0 + BPR_ALPHA * (flow / np.maximum(cap, 1e-6)) ** BPR_BETA)


# ─────────────────────────────────────────────────────────────────────────────
# Road-type lookup tables: capacity (veh/hr) and free-flow speed (km/h)
# ─────────────────────────────────────────────────────────────────────────────
CAPACITY = {
    "motorway": 2200, "motorway_link": 1500, "trunk": 1800, "trunk_link": 1200,
    "primary": 1500, "primary_link": 1000, "secondary": 1000, "secondary_link": 700,
    "tertiary": 700, "tertiary_link": 500, "residential": 400, "living_street": 200,
    "unclassified": 500, "road": 500,
}
SPEED = {
    "motorway": 100, "motorway_link": 80, "trunk": 80, "trunk_link": 60,
    "primary": 60, "primary_link": 50, "secondary": 50, "secondary_link": 40,
    "tertiary": 40, "tertiary_link": 30, "residential": 30, "living_street": 20,
    "unclassified": 40, "road": 40,
}


def get_cap(hw):
    """Capacity (vehicles/hour) for an OSM highway-class tag (string or list)."""
    if isinstance(hw, list):
        hw = hw[0]
    return CAPACITY.get(str(hw), 500)


def get_spd(hw):
    """Free-flow speed (km/h) for an OSM highway-class tag (string or list)."""
    if isinstance(hw, list):
        hw = hw[0]
    return SPEED.get(str(hw), 40)
