"""
braess — Braess Paradox Road Redundancy Detector

    from braess import run_braess_analysis
    summary, df, G = run_braess_analysis(point=(12.9352, 77.6245), use_synthetic=False)

See run_analysis.py at the project root for the script you actually edit
and run day to day.
"""
from .pipeline import run_braess_analysis
from .network import load_network, load_osm_network, build_synthetic_city
from .equilibrium import frank_wolfe_ue, generate_od_demand, all_or_nothing
from .detection import detect_braess_edges, screen_candidates, add_betweenness
from .visualize import plot_static_map, plot_dashboard, plot_top_braess, export_results

__all__ = [
    "run_braess_analysis",
    "load_network", "load_osm_network", "build_synthetic_city",
    "frank_wolfe_ue", "generate_od_demand", "all_or_nothing",
    "detect_braess_edges", "screen_candidates", "add_betweenness",
    "plot_static_map", "plot_dashboard", "plot_top_braess", "export_results",
]
