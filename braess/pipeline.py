"""
Pipeline orchestrator — wires together network loading, traffic equilibrium,
Braess detection, and visualisation/export into a single call.

This is the function you actually call from your own script:

    from braess import run_braess_analysis
    summary, df, G = run_braess_analysis(point=(12.9352, 77.6245), ...)
"""
import os
import time

from .network import load_network
from .equilibrium import frank_wolfe_ue, generate_od_demand
from .detection import detect_braess_edges, add_betweenness
from .visualize import plot_static_map, plot_dashboard, plot_top_braess, export_results


def run_braess_analysis(
    place_name=None,
    point=None,
    dist_m=1500,
    use_synthetic=True,
    grid_rows=12, grid_cols=12,
    n_braess_motifs=6,
    output_dir="/mnt/user-data/outputs/braess_output",
    num_od_pairs=80,
    total_demand=14000,
    motif_demand=1000,
    top_k_candidates=60,
    n_control=15,
    fw_max_iter=300,
    fw_detection_iter=150,
    fw_tol=1e-6,
    convergence_warn_threshold=1e-3,
):
    """
    Run the full Braess-paradox detection pipeline end to end.

    Parameters
    ----------
    place_name : str, optional
        OSM polygon query, e.g. "Koramangala, Bengaluru, India". Many
        informal neighbourhood names have no administrative boundary in
        OSM and will fail — prefer `point` for those.
    point : (lat, lon) tuple, optional
        OSM point+radius query. Works for any location regardless of
        whether it has an OSM polygon. Takes priority over place_name if
        both are given.
    dist_m : float
        Radius in metres around `point` to pull roads from.
    use_synthetic : bool
        If True, skip OSM entirely and use the synthetic city generator
        (with embedded, validated Braess motifs as ground truth).
    total_demand : float
        Background vehicle-trips spread across num_od_pairs random OD
        pairs. This is the main lever for how congested the network gets —
        too low and BPR costs stay flat (no Braess effect possible), too
        high and Frank-Wolfe convergence can degrade. Check the printed
        gap and the `vc_ratio` column in the output CSV; aim for most
        values landing roughly between 0.3 and 1.3.
    motif_demand : float
        Extra demand targeted directly at embedded synthetic motifs.
        Has no effect on a real OSM network — leave at 0 for those.

    Returns
    -------
    (summary, df, G) : (dict, pandas.DataFrame, networkx.DiGraph)
        summary is the same dict written to braess_summary.json.
        df is the same table written to braess_results.csv.
    """
    t0 = time.time()
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("  BRAESS PARADOX RESEARCH PLATFORM")
    print("=" * 60)

    # 1. Load
    G, source = load_network(place_name, use_synthetic, grid_rows, grid_cols, n_braess_motifs,
                              point=point, dist_m=dist_m)
    print(f"      Source: {source.upper()}")

    # 2. Demand + baseline UE
    od = generate_od_demand(G, num_od_pairs, total_demand, motif_demand=motif_demand)
    print(f"\n[2/4] Running Frank-Wolfe UE  ({len(od)} OD pairs, "
          f"{sum(od.values()):.0f} total vehicle-trips) ...")
    bl_flows, bl_cost, gaps = frank_wolfe_ue(G, od, max_iter=fw_max_iter, tol=fw_tol, verbose=True)
    print(f"      Baseline system cost: {bl_cost:.2f} min·veh  "
          f"(converged in {len(gaps)} iters, gap={gaps[-1]:.2e})")
    if gaps[-1] > convergence_warn_threshold:
        print(f"      ⚠ WARNING: relative gap {gaps[-1]:.2e} exceeds "
              f"{convergence_warn_threshold:.0e} — results below may include "
              f"non-convergence noise rather than genuine Braess effects. "
              f"Consider increasing fw_max_iter or lowering motif_demand/total_demand.")

    # 3. Detect + score
    df = detect_braess_edges(G, od, bl_cost, bl_flows,
                              top_k=top_k_candidates, n_control=n_control,
                              fw_iters=fw_detection_iter, fw_tol=1e-5)
    if df.empty:
        print("No flow-carrying edges found to test. Try higher total_demand.")
        return None
    df = add_betweenness(G, df)

    # 4. Visualise + export
    print("\n[4/4] Generating outputs ...")
    plot_static_map(G, df, output_dir)
    plot_dashboard(df, gaps, output_dir)
    plot_top_braess(G, df, output_dir)
    summary = export_results(df, bl_cost, output_dir)

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  Done in {elapsed:.1f}s")
    print(f"  Braess edges:    {summary['braess_edges_found']} / {summary['edges_tested']} tested "
          f"({summary['braess_rate_pct']}%)")
    print(f"  Reliable (gap<1e-3): {summary['braess_edges_reliable']} braess / {summary['edges_reliable']} reliable tests")
    if summary['braess_edges_found'] > 0:
        print(f"  Max improvement: {summary['max_improvement_pct']:.3f}%  "
              f"(avg {summary['avg_improvement_braess_pct']:.3f}%)")
    print(f"  Outputs → {output_dir}")
    print(f"{'='*60}")
    return summary, df, G
