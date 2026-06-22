
# BraessNet

**A research-grade platform for detecting Braess's Paradox in real urban road networks.**

Braess's Paradox is the counterintuitive transportation phenomenon where *adding* a road to a network can make *everyone's* travel time worse — and, conversely, *removing* the right road can make traffic flow better for the whole system, even though it looks like a loss of capacity. BraessNet automatically scans real city road networks (pulled from OpenStreetMap) to find road segments that are actively causing exactly this effect.

This project applies the theory to three real Indian urban areas — **Koramangala (Bengaluru)**, **Whitefield (Bengaluru)**, and **Lajpat Nagar (Delhi)** — and quantifies how much each "paradox edge" is costing the system in aggregate travel time.

## Why this matters

Indian cities are growing road networks faster than they can be planned holistically. This tool gives urban planners a way to flag specific intersections or links worth re-evaluating — not based on intuition, but on a traffic equilibrium simulation grounded in real network topology and real demand assumptions.

## Results

Each city's network was tested by removing each candidate edge one at a time, re-solving for traffic equilibrium, and measuring the system-wide change in total travel cost.

| Area | Edges Tested | Braess Edges Found | Braess Rate | Max Improvement (single edge) | Baseline System Cost (min·veh) |
|---|---|---|---|---|---|
| **Whitefield** | 75 | 10 | 13.3% | **−12.02%** | 26,159.5 |
| **Lajpat Nagar** | 75 | 11 | 14.7% | −4.55% | 30,426.8 |
| **Koramangala** | 75 | 6 | 8.0% | −7.74% | 27,807.9 |
| **Total / Avg** | 225 | 27 | 12.0% | — | — |

*(Negative % = improvement in total system travel time when the edge is removed.)*

### Key findings

- **Whitefield** showed the single largest improvement: removing one tertiary road segment cuts total system travel time by **12%**, the strongest paradox signal across all three areas.
- **Lajpat Nagar** flagged a multi-edge Braess motif along **Mathura Road**, a named primary arterial — a rare case where the paradox isn't confined to small residential cut-throughs but appears on a major thoroughfare.
- Across all three areas, roughly **1 in 8 candidate edges** tested positive for Braess's Paradox, suggesting this isn't a rare edge case but a structurally common feature of how these networks evolved.

Full per-city output (interactive HTML dashboard, network map, all flagged edges, raw CSV) is available in [`results/`](./results).

## Methodology

1. **Network extraction** — real road geometry and topology for each area is pulled from OpenStreetMap (cached locally after first download) (`braess/network.py`)
2. **Demand modeling** — origin-destination travel demand is generated for the area (`braess/equilibrium.py`)
3. **Equilibrium solving** — a Frank-Wolfe algorithm computes how traffic actually distributes itself across the network under congestion, using BPR (Bureau of Public Roads) link cost functions for realistic congestion-dependent travel times (`braess/constants.py`, `braess/equilibrium.py`)
4. **Paradox detection** — each candidate edge is screened, then individually removed; the network is re-solved to equilibrium; and the change in total system travel cost is measured. Edges whose removal *improves* total system cost are flagged as exhibiting Braess's Paradox (`braess/detection.py`)
5. **Output generation** — results are written out as an interactive dashboard, annotated map, and structured CSV/JSON (`braess/visualize.py`)

These steps are wired together by `braess/pipeline.py` via a single entry point, `run_braess_analysis()`.

## Architecture

```
BraessNet/
├── run_analysis.py        # entry point — set coordinates, demand, output folder here
├── braess/
│   ├── __init__.py
│   ├── constants.py        # BPR cost function + road-type capacity/speed tables
│   ├── network.py          # OSM network download (with caching) + synthetic test city
│   ├── equilibrium.py      # Frank-Wolfe traffic equilibrium solver
│   ├── detection.py        # edge screening + removal testing
│   ├── visualize.py        # map, dashboard, CSV/JSON output generation
│   └── pipeline.py         # run_braess_analysis() — orchestrates the above
├── results/
│   ├── koramangala/
│   ├── lajpat_nagar/
│   └── whitefield/
└── requirements.txt
```

## Running it

```bash
pip install -r requirements.txt
python run_analysis.py
```

To analyze a new area, edit the parameters at the top of `run_analysis.py`:

```python
run_braess_analysis(
    point=(LAT, LON),
    dist_m=1500,
    use_synthetic=False,
    output_dir=r"path/to/output/folder",
    total_demand=8000,   # tune per area
    motif_demand=0,
)
```

Coordinates for any area can be found via Google Maps → right-click the location → "What's here?".

## Roadmap

- [ ] Extend analysis to additional Indian metro areas
- [ ] Sensitivity analysis on `total_demand` calibration
- [ ] Compare detected Braess edges against actual traffic incident/congestion data where available

## License

MIT

