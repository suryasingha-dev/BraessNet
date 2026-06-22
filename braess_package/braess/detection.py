"""
Module 3 — Braess Detection & Redundancy Scoring.

For each candidate road: remove it, re-solve the full Wardrop equilibrium,
and check whether total system travel time went DOWN. If it did, that road
is a genuine Braess edge — it's actively making traffic worse by existing.

Testing every edge in a large network this way is expensive (each test is a
full equilibrium re-solve), so screen_candidates() does a cheap, no-re-solve
pre-pass to short-list which edges are worth the expensive test.
"""
import numpy as np
import pandas as pd
import networkx as nx

from .constants import BPR_ALPHA, BPR_BETA
from .equilibrium import frank_wolfe_ue


def bpr_marginal_cost(flow, fft, cap):
    """d(cost)/d(flow) for BPR — used for cheap Braess screening."""
    return fft * BPR_ALPHA * BPR_BETA * (np.maximum(flow, 0) ** (BPR_BETA - 1)) / (np.maximum(cap, 1e-6) ** BPR_BETA)


def shortcut_suspicion_score(flow, cap):
    """
    'Free lunch' proxy: high absolute flow combined with low utilisation.
    A classic Braess bypass attracts heavy flow (everyone wants the shortcut)
    while staying far from its own capacity (it's a small, fast link) — so it
    never shows up as congested by marginal-social-cost screening alone, yet
    removing it is exactly what forces traffic onto worse, congested routes.
    """
    vc = flow / max(cap, 1e-6)
    return flow * (1 - min(vc, 1.0))


def screen_candidates(G, baseline_flows, top_k=60, min_flow=1.0):
    """
    Cheap (no re-solve) two-signal screening pass over all flow-carrying edges:
      1. Marginal social cost (flow * d(cost)/d(flow)) — finds congested
         edges whose removal relieves system stress (Pigouvian proxy).
      2. Shortcut suspicion (flow * (1 - v/c)) — finds heavily-used but
         uncongested edges, the structural signature of a Braess bypass,
         which signal (1) alone systematically misses because a bypass by
         design never congests itself.
    Top-K/2 from each signal are combined (deduplicated) into the candidate
    set, since brute-force testing every edge does not scale on larger
    networks.
    """
    msc_scored, suspicion_scored = [], []
    for u, v, d in G.edges(data=True):
        f = baseline_flows.get((u, v), 0.0)
        if f < min_flow:
            continue
        mc = bpr_marginal_cost(f, d["free_flow_time"], d["capacity"])
        msc_scored.append((u, v, f * mc))
        suspicion_scored.append((u, v, shortcut_suspicion_score(f, d["capacity"])))

    msc_scored.sort(key=lambda r: -r[2])
    suspicion_scored.sort(key=lambda r: -r[2])

    half = max(top_k // 2, 1)
    chosen = {(u, v) for u, v, _ in msc_scored[:half]}
    chosen |= {(u, v) for u, v, _ in suspicion_scored[:half]}
    # Top up to top_k from the marginal-cost list if dedup left room
    for u, v, _ in msc_scored:
        if len(chosen) >= top_k:
            break
        chosen.add((u, v))
    return list(chosen)[:top_k] if len(chosen) > top_k else list(chosen)


def detect_braess_edges(G, od_demand, baseline_cost, baseline_flows,
                        top_k=60, n_control=15, fw_iters=80, fw_tol=1e-6):
    """
    Two-stage Braess detection:
      1. Screen all flow-carrying edges via the two-signal proxy (cheap).
      2. Re-solve full Wardrop UE with each top-K candidate edge removed
         (expensive but bounded), plus a random control sample of
         flow-carrying edges NOT in the top-K, so the reported Braess rate
         isn't artificially inflated by only ever testing "suspicious" edges.

    Every test's convergence gap is tracked (see equilibrium.frank_wolfe_ue)
    and a 'reliable' flag (gap < 1e-3) is attached, since Frank-Wolfe's slow
    tail convergence means an under-converged comparison can fabricate a
    small spurious Braess signal in either direction.
    """
    candidates = screen_candidates(G, baseline_flows, top_k=top_k)

    flow_edges = [(u, v) for u, v, d in G.edges(data=True)
                  if baseline_flows.get((u, v), 0.0) >= 1.0]
    rng = np.random.default_rng(0)
    remaining = [e for e in flow_edges if e not in set(candidates)]
    n_ctrl = min(n_control, len(remaining))
    control = [tuple(e) for e in rng.choice(remaining, n_ctrl, replace=False)] if n_ctrl > 0 else []

    test_set = candidates + control
    print(f"\n[3/4] Braess detection: {len(candidates)} screened candidates + "
          f"{len(control)} random control edges = {len(test_set)} full re-solves "
          f"(baseline = {baseline_cost:.2f} min·veh) ...")

    records = []
    for idx, (u, v) in enumerate(test_set):
        if not G.has_edge(u, v):
            continue
        edata = G[u][v].copy()
        G.remove_edge(u, v)
        try:
            _, cost, test_gaps = frank_wolfe_ue(G, od_demand, max_iter=fw_iters, tol=fw_tol)
            final_gap = test_gaps[-1] if test_gaps else float("nan")
        except Exception:
            cost = baseline_cost
            final_gap = float("nan")
        G.add_edge(u, v, **edata)

        delta = cost - baseline_cost
        hw = edata.get("highway", "unclassified")
        if isinstance(hw, list):
            hw = hw[0]
        bl_flow = baseline_flows.get((u, v), 0.0)
        cap = edata.get("capacity", 500)

        records.append(dict(
            u=u, v=v, highway=hw,
            street_name=edata.get("street_name", "(unnamed road)"),
            is_screened_candidate=(u, v) in set(candidates),
            length_m=round(edata.get("length", 0), 1),
            free_flow_time_min=round(edata.get("free_flow_time", 0), 3),
            capacity_veh_hr=cap,
            baseline_flow=round(bl_flow, 2),
            vc_ratio=round(bl_flow / max(cap, 1), 4),
            system_cost_without=round(cost, 4),
            system_cost_baseline=round(baseline_cost, 4),
            delta_cost=round(delta, 4),
            pct_change=round(delta / baseline_cost * 100, 4),
            is_braess=bool(delta < -1e-6),
            convergence_gap=final_gap,
            reliable=bool(final_gap < 1e-3),
        ))
        if (idx + 1) % 10 == 0:
            nb = sum(r["is_braess"] for r in records)
            print(f"      {idx+1}/{len(test_set)} tested | Braess found: {nb}")

    df = pd.DataFrame(records)
    if df.empty:
        return df

    n_unreliable = (~df["reliable"]).sum()
    if n_unreliable > 0:
        print(f"      ⚠ {n_unreliable}/{len(df)} edge tests did not reach tight "
              f"convergence (gap ≥ 1e-3) — flagged as unreliable=False in results, "
              f"treat their is_braess label with caution.")

    # Redundancy score: 60% Braess magnitude + 40% under-utilisation
    df["braess_mag"] = df["delta_cost"].clip(upper=0).abs()
    mx = df["braess_mag"].max()
    df["braess_norm"] = df["braess_mag"] / max(mx, 1e-9)
    df["vc_redundancy"] = 1 - df["vc_ratio"].clip(0, 1)
    df["redundancy_score"] = 0.6 * df["braess_norm"] + 0.4 * df["vc_redundancy"]
    df.sort_values("redundancy_score", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)

    n_reliable_braess = int((df["is_braess"] & df["reliable"]).sum())
    print(f"\n      ✓ Braess edges: {df['is_braess'].sum()} / {len(df)} "
          f"({n_reliable_braess} with reliable convergence)")
    if df["is_braess"].any():
        print(f"      ✓ Max improvement: {df['pct_change'].min():.3f}%")
    return df


def add_betweenness(G, df, k=150):
    """Enrich results with edge betweenness centrality (approximated via k-sample)."""
    print("      Computing edge betweenness centrality ...")
    ebc = nx.edge_betweenness_centrality(
        G, k=min(k, G.number_of_nodes()), weight="cost", normalized=True)
    df["betweenness"] = df.apply(
        lambda r: ebc.get((r.u, r.v), ebc.get((r.v, r.u), 0)), axis=1)
    return df
