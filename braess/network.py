"""
Module 1 — Network Ingestion.

Two ways to get a road network:
  - build_synthetic_city(): grid + ring + deliberately embedded Braess motifs.
    Always works, no internet required, has known ground truth.
  - load_osm_network(): real city via OSMnx, with disk caching for
    reproducibility. Requires internet access to OpenStreetMap.

load_network() is the single entry point both other modules should call —
it picks between the two and normalises the result.
"""
import os
import numpy as np
import networkx as nx

from .constants import get_cap, get_spd


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic City Generator
# ─────────────────────────────────────────────────────────────────────────────

def build_synthetic_city(rows=12, cols=12, seed=42, n_braess_motifs=6):
    """
    Build a synthetic directed city graph with:
      - Grid backbone (residential / secondary)
      - Arterial corridors (primary)
      - Ring road (primary)
      - Deliberately embedded Braess motifs: pairs of congestion-sensitive
        legs (low capacity, low free-flow-time) connected by a near-zero-cost
        "shortcut" link, structurally identical to the classic 4-node Braess
        network (Braess, 1968) validated against closed-form equilibria.

    Without the motifs, generic grid topologies rarely contain the precise
    structural condition needed for Braess's paradox (a bypass that's locally
    attractive but globally harmful), so they are inserted explicitly rather
    than hoped for — exactly as real cities have specific junctions
    (e.g. a new connector road) where the paradox is observed in practice.

    Each node has x,y coords. Each edge has full BPR attributes.
    """
    rng = np.random.default_rng(seed)
    G = nx.DiGraph()
    NODE_SPACING = 0.005   # ~550 m in degrees

    for r in range(rows):
        for c in range(cols):
            nid = r * cols + c
            G.add_node(nid,
                       x=c * NODE_SPACING + rng.uniform(-0.0003, 0.0003),
                       y=r * NODE_SPACING + rng.uniform(-0.0003, 0.0003))

    def add_edge(u, v, hw, fft_override=None, cap_override=None):
        xu, yu = G.nodes[u]['x'], G.nodes[u]['y']
        xv, yv = G.nodes[v]['x'], G.nodes[v]['y']
        dist_deg = ((xu - xv) ** 2 + (yu - yv) ** 2) ** 0.5
        length_m = dist_deg * 111_000
        spd = get_spd(hw)
        cap = cap_override if cap_override is not None else get_cap(hw)
        fft = fft_override if fft_override is not None else (length_m / 1000) / spd * 60
        for a, b in [(u, v), (v, u)]:
            G.add_edge(a, b, highway=hw, length=length_m,
                       free_flow_time=fft, capacity=cap,
                       flow=0.0, cost=fft, is_motif=False,
                       street_name=f"Synthetic {hw} link {a}-{b}")

    # 1. Grid backbone
    for r in range(rows):
        for c in range(cols):
            u = r * cols + c
            is_arterial_row = (r % 3 == 0)
            is_arterial_col = (c % 3 == 0)
            if c + 1 < cols:
                hw = "primary" if is_arterial_row else ("secondary" if r % 2 == 0 else "residential")
                add_edge(u, u + 1, hw)
            if r + 1 < rows:
                hw = "primary" if is_arterial_col else ("secondary" if c % 2 == 0 else "residential")
                add_edge(u, u + cols, hw)

    # 2. Ring road around perimeter
    perimeter = (
        [r * cols + 0 for r in range(rows)] +
        [(rows - 1) * cols + c for c in range(1, cols)] +
        [(rows - 1 - r) * cols + (cols - 1) for r in range(1, rows)] +
        [c for c in range(cols - 2, 0, -1)]
    )
    for i in range(len(perimeter) - 1):
        add_edge(perimeter[i], perimeter[i + 1], "primary")

    # 3. Embedded Braess motifs.
    #    Structural template (validated against the BPR/Frank-Wolfe solver
    #    using the classic 4-node Braess topology):
    #      S -> A : congestion-sensitive   (low cap, low fft)
    #      A -> T : fixed-cost alternative (high cap, moderate fft)
    #      S -> B : fixed-cost alternative (high cap, moderate fft)
    #      B -> T : congestion-sensitive   (low cap, low fft)
    #      A -> B : near-zero-cost bypass  (the literal "extra road")
    #    A regular grid has 2x2 blocks with exactly this S/A/B/T shape, so
    #    we pick well-separated 2x2 blocks and overwrite their edge
    #    attributes plus add the diagonal bypass.
    motif_count = 0
    motif_od_pairs = []
    candidates = []
    for r in range(1, rows - 2, 2):
        for c in range(1, cols - 2, 2):
            candidates.append((r, c))
    rng.shuffle(candidates)

    for (r, c) in candidates:
        if motif_count >= n_braess_motifs:
            break
        S = r * cols + c
        A = r * cols + (c + 1)
        B = (r + 1) * cols + c
        T = (r + 1) * cols + (c + 1)
        if not all(G.has_edge(*e) for e in [(S, A), (B, T), (S, B), (A, T)]):
            continue

        # Congestion-sensitive legs: low capacity, low free-flow time.
        # Parameters grid-searched against the isolated 4-node Braess
        # network to ensure (a) a genuine, large Braess effect and
        # (b) clean Frank-Wolfe convergence (gap < 1e-4) at this loading —
        # earlier parameter choices produced oscillating, non-convergent
        # equilibria that masqueraded as spurious small "Braess" signals.
        for (u, v) in [(S, A), (B, T)]:
            for a, b in [(u, v), (v, u)]:
                if G.has_edge(a, b):
                    G[a][b].update(free_flow_time=0.5, capacity=600,
                                   highway="residential", cost=0.5, is_motif=True)
        # Fixed-cost alternative legs: high capacity, higher free-flow time
        for (u, v) in [(S, B), (A, T)]:
            for a, b in [(u, v), (v, u)]:
                if G.has_edge(a, b):
                    G[a][b].update(free_flow_time=10.0, capacity=20000,
                                   highway="secondary", cost=10.0, is_motif=True)
        # Bypass A-B: near-zero free-flow time, generous capacity.
        # CRITICAL: must be ONE-WAY (A->B only). A bidirectional bypass
        # behaves as genuine extra network capacity and does NOT reproduce
        # Braess's paradox — this was verified against the classic 4-node
        # network (Braess, 1968): the paradox requires a directed shortcut
        # that's attractive in the direction of flow but offers no
        # reciprocal benefit, matching how a one-way connector road or a
        # newly opened one-way link behaves in practice.
        xa, ya = G.nodes[A]['x'], G.nodes[A]['y']
        xb, yb = G.nodes[B]['x'], G.nodes[B]['y']
        dist_m = (((xa - xb) ** 2 + (ya - yb) ** 2) ** 0.5) * 111_000
        G.add_edge(A, B, highway="tertiary", length=dist_m,
                   free_flow_time=0.05, capacity=20000,
                   flow=0.0, cost=0.05, is_motif=True, is_bypass=True,
                   street_name=f"Synthetic bypass {A}-{B}")
        motif_count += 1
        motif_od_pairs.append((S, T))

    # Keep largest SCC
    scc = max(nx.strongly_connected_components(G), key=len)
    G = G.subgraph(scc).copy()
    motif_od_pairs = [(s, t) for s, t in motif_od_pairs if s in G and t in G]
    G.graph["motif_od_pairs"] = motif_od_pairs
    print(f"      Synthetic city: {rows}×{cols} grid | "
          f"{G.number_of_nodes()} nodes | {G.number_of_edges()} edges | "
          f"{motif_count} embedded Braess motifs")
    return G


# ─────────────────────────────────────────────────────────────────────────────
# Real OSMnx Loader
# ─────────────────────────────────────────────────────────────────────────────

def load_osm_network(place_name=None, network_type="drive", cache_dir="osm_cache",
                      force_redownload=False, point=None, dist_m=1500):
    """
    Download real city from OpenStreetMap via OSMnx, with disk caching.

    Two query modes:
      - place_name (polygon query): works for cities, wards, and localities
        that have an administrative boundary polygon in OSM. Many informal
        neighbourhood names (e.g. "Koramangala") do NOT have one and will
        fail geocoding even though the area itself is well-mapped — OSM's
        Nominatim geocoder requires a (Multi)Polygon match for
        graph_from_place(), and an informal locality is often just a point
        label with no drawn boundary.
      - point=(lat, lon) + dist_m (radius query): works for ANY location
        regardless of whether it has an administrative polygon, by pulling
        every road within dist_m metres of a coordinate. This is the
        reliable choice for neighbourhood-level "is there a Braess effect
        in this specific area" studies. If place_name geocoding fails and
        no point is given, you'll need to supply lat/lon manually (e.g. via
        Google Maps "right click -> what's here").

    IMPORTANT: OpenStreetMap is a live, continuously-edited dataset, so
    repeated downloads of the same area are not guaranteed identical run to
    run. The downloaded graph is pickled to disk and reused on every
    subsequent call with the same query, so results stay reproducible.
    Delete the relevant cache file (or pass force_redownload=True) to force
    a fresh OSM pull.
    """
    import pickle, hashlib
    os.makedirs(cache_dir, exist_ok=True)
    if point is not None:
        cache_key_str = f"point:{point[0]:.5f},{point[1]:.5f}|{dist_m}|{network_type}"
    else:
        cache_key_str = f"place:{place_name}|{network_type}"
    key = hashlib.md5(cache_key_str.encode()).hexdigest()[:12]
    cache_path = os.path.join(cache_dir, f"{key}.gpickle")

    if os.path.exists(cache_path) and not force_redownload:
        print(f"      Loading cached OSM graph ({cache_key_str}) -> {cache_path} ...")
        with open(cache_path, "rb") as f:
            G = pickle.load(f)
        print(f"      Cached graph: {G.number_of_nodes()} nodes | {G.number_of_edges()} edges")
        return G

    try:
        import osmnx as ox
        ox.settings.log_console = False

        if point is not None:
            print(f"      Downloading OSM network: point {point}, radius {dist_m}m ...")
            G_raw = ox.graph_from_point(point, dist=dist_m, network_type=network_type, simplify=True)
        else:
            print(f"      Downloading OSM network: '{place_name}' (polygon query) ...")
            G_raw = ox.graph_from_place(place_name, network_type=network_type, simplify=True)

        G = ox.convert.to_digraph(G_raw, weight="length")
        scc = max(nx.strongly_connected_components(G), key=len)
        G = G.subgraph(scc).copy()
        for u, v, data in G.edges(data=True):
            hw = data.get("highway", "unclassified")
            spd = get_spd(hw)
            cap = get_cap(hw)
            lm = data.get("length", 100)
            fft = (lm / 1000) / spd * 60
            # OSM 'name' tag: can be a single string, a list (multiple names
            # for the same way, e.g. bilingual signage), or absent entirely
            # (common for short connector/service roads with no signposted
            # name). Normalise to one clean string for downstream use.
            raw_name = data.get("name")
            if isinstance(raw_name, list):
                street_name = " / ".join(raw_name)
            elif isinstance(raw_name, str) and raw_name.strip():
                street_name = raw_name
            else:
                street_name = "(unnamed road)"
            data.update(free_flow_time=fft, capacity=cap, flow=0.0, cost=fft,
                        street_name=street_name)
        print(f"      OSM graph: {G.number_of_nodes()} nodes | {G.number_of_edges()} edges")

        with open(cache_path, "wb") as f:
            pickle.dump(G, f)
        print(f"      Cached to {cache_path} for reproducible future runs.")
        return G
    except Exception as e:
        if point is None:
            print(f"      OSMnx polygon query failed ({e}).")
            print(f"      '{place_name}' likely has no administrative boundary polygon in OSM "
                  f"(common for informal neighbourhood names). Falling back to synthetic city. "
                  f"To use real data for this area instead, pass point=(lat, lon) — "
                  f"look up coordinates via Google Maps right-click -> 'What's here?'.")
        else:
            print(f"      OSMnx point query failed ({e}). Falling back to synthetic city.")
        return None


def load_network(place_name=None, use_synthetic=False, rows=12, cols=12, n_braess_motifs=6,
                  point=None, dist_m=1500):
    """Master loader – tries OSMnx first (polygon or point query), falls back to synthetic."""
    print("[1/4] Loading road network ...")
    if not use_synthetic and (place_name or point):
        G = load_osm_network(place_name, point=point, dist_m=dist_m)
        if G is not None:
            G.graph.setdefault("motif_od_pairs", [])
            return G, "osm"
    G = build_synthetic_city(rows=rows, cols=cols, n_braess_motifs=n_braess_motifs)
    return G, "synthetic"
