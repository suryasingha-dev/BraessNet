"""
Module 2 — Traffic Assignment.

Computes Wardrop User Equilibrium (UE) flows: the state where no driver can
reduce their own travel time by switching routes, given everyone else's
choices. This is the only correct way to model how selfish routing interacts
with congestion — which is what Braess's paradox is actually about.

frank_wolfe_ue() is the solver; generate_od_demand() builds the
origin-destination trip matrix it solves for.
"""
import numpy as np
import networkx as nx
from collections import defaultdict

from .constants import bpr_cost_vec


def all_or_nothing(G, od_demand):
    """Route all demand along current-cost shortest paths."""
    edge_flows = defaultdict(float)
    for (o, d), demand in od_demand.items():
        if o == d or demand <= 0:
            continue
        try:
            path = nx.shortest_path(G, o, d, weight="cost")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue
        for i in range(len(path) - 1):
            edge_flows[(path[i], path[i + 1])] += demand
    return edge_flows


def update_costs(G, edge_flows):
    """Standalone helper for ad-hoc inspection (not used internally by frank_wolfe_ue)."""
    for u, v, data in G.edges(data=True):
        flow = edge_flows.get((u, v), 0.0)
        data["flow"] = flow
        data["cost"] = bpr_cost_vec(np.array([flow]), np.array([data["free_flow_time"]]),
                                     np.array([data["capacity"]]))[0]


def frank_wolfe_ue(G, od_demand, max_iter=60, tol=1e-4, verbose=False):
    """
    Frank-Wolfe algorithm -> Wardrop User Equilibrium flows.

    Vectorised cost/line-search math (numpy); the AON shortest-path step
    uses networkx, since that's the genuinely combinatorial part that
    doesn't vectorise.

    Returns (flow_dict, system_cost, gap_history). gap_history is the
    relative-gap convergence metric at every iteration — check
    gap_history[-1] before trusting any comparison between two solves,
    since Frank-Wolfe has notoriously slow tail convergence and comparing
    two under-converged equilibria can produce spurious deltas in either
    direction.
    """
    edges = list(G.edges())
    n = len(edges)
    eidx = {e: i for i, e in enumerate(edges)}
    fft = np.array([G[u][v]["free_flow_time"] for u, v in edges])
    cap = np.array([G[u][v]["capacity"] for u, v in edges])

    for u, v, data in G.edges(data=True):
        data["cost"] = data["free_flow_time"]

    def aon_array():
        ef = all_or_nothing(G, od_demand)
        arr = np.zeros(n)
        for e, f in ef.items():
            if e in eidx:
                arr[eidx[e]] = f
        return arr

    def set_costs(arr):
        costs = bpr_cost_vec(arr, fft, cap)
        for e, i in eidx.items():
            G[e[0]][e[1]]["cost"] = costs[i]
        return costs

    x = aon_array()
    set_costs(x)
    gaps = []

    for it in range(1, max_iter + 1):
        y = aon_array()
        costs_x = bpr_cost_vec(x, fft, cap)
        num = np.sum(costs_x * (x - y))
        den = np.sum(costs_x * x)
        gap = abs(num / den) if den > 1e-9 else 0.0
        gaps.append(gap)
        if gap < tol:
            if verbose:
                print(f"      UE converged at iteration {it} | gap = {gap:.2e}")
            break

        diff = y - x
        def deriv(alpha):
            return np.sum(bpr_cost_vec(x + alpha * diff, fft, cap) * diff)

        lo, hi = 0.0, 1.0
        d_lo, d_hi = deriv(0.0), deriv(1.0)
        if d_lo >= 0:
            alpha = 0.0
        elif d_hi <= 0:
            alpha = 1.0
        else:
            for _ in range(25):
                mid = (lo + hi) / 2
                if deriv(mid) > 0:
                    hi = mid
                else:
                    lo = mid
            alpha = (lo + hi) / 2

        x = x + alpha * diff
        set_costs(x)

    sc = float(np.sum(x * bpr_cost_vec(x, fft, cap)))
    flow_dict = {e: x[i] for e, i in eidx.items()}
    return flow_dict, sc, gaps


def generate_od_demand(G, num_pairs=30, total_demand=1000, seed=42, motif_demand=2000):
    """
    Sample background OD demand across the network, AND inject deliberate
    stress-test demand on any embedded Braess motifs (G.graph['motif_od_pairs']).

    Rationale: Braess's paradox is a property of how a SPECIFIC origin-
    destination flow interacts with a specific pair of routes. Generic
    random OD sampling spreads demand thinly across the whole network and
    essentially never loads any single S->T motif heavily enough to expose
    the effect — this mirrors why real-world Braess cases are documented at
    specific, identifiable corridors (e.g. Cheonggyecheon, Seoul) rather than
    "discovered" by averaging traffic over an entire city. A real traffic
    study targets known bottleneck corridors the same way. On a real OSM
    network (no embedded motifs), motif_demand has no effect and can be
    left at 0.
    """
    rng = np.random.default_rng(seed)
    nodes = list(G.nodes())
    n = min(len(nodes), 150)
    sample = rng.choice(nodes, n, replace=False).tolist()
    od = {}
    attempts = 0
    while len(od) < num_pairs and attempts < num_pairs * 20:
        o, d = rng.choice(sample, 2, replace=False)
        if (o, d) not in od and o != d:
            od[(o, d)] = total_demand / num_pairs
        attempts += 1

    motif_pairs = G.graph.get("motif_od_pairs", [])
    for (s, t) in motif_pairs:
        if s in G and t in G:
            od[(s, t)] = od.get((s, t), 0) + motif_demand

    return od
