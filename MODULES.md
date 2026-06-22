# Braess Paradox Detector — Module Map

This is the same tool as before, split into separate files so each piece is
easier to read and edit on its own. Logic is unchanged — running this
produces identical results to the single-file version.

## What you actually edit

**`run_analysis.py`** — the only file you need to open day to day. Change
the coordinates, demand, and output folder here for each area you study.

## What's inside `braess/` (you shouldn't need to touch these)

| File | What it does |
|---|---|
| `constants.py` | BPR cost function + road-type capacity/speed tables |
| `network.py` | Downloads real OSM road networks (with caching) or builds the synthetic test city |
| `equilibrium.py` | Frank-Wolfe solver — computes how traffic actually distributes itself under congestion |
| `detection.py` | Tests each road: does removing it make traffic better or worse system-wide? |
| `visualize.py` | Generates the map, dashboard, and CSV/JSON output files |
| `pipeline.py` | `run_braess_analysis()` — wires the above together in order |
| `__init__.py` | Lets you write `from braess import run_braess_analysis` |

## Running it

```
pip install -r requirements.txt
python run_analysis.py
```

## Switching areas

Edit the block at the top of `run_analysis.py`:

```python
run_braess_analysis(
    point=(LAT, LON),
    dist_m=1500,
    use_synthetic=False,
    output_dir=r"C:\path\to\output\folder",
    total_demand=8000,   # tune per area
    motif_demand=0,
)
```

Coordinates for an area: right-click the location on Google Maps -> "What's
here?" -> copy the lat, lon shown.

## If you need to change the methodology

- Tweak road capacities/speeds -> `braess/constants.py`
- Change how demand is generated -> `braess/equilibrium.py` ->
  `generate_od_demand()`
- Change which roads get tested / how candidates are screened ->
  `braess/detection.py` -> `screen_candidates()`
- Change convergence thresholds or iteration counts -> passed as arguments
  to `run_braess_analysis()` in `run_analysis.py`, no need to edit
  `pipeline.py` itself unless you want different defaults
