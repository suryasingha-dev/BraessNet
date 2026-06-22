"""
This is the ONLY file you need to edit for day-to-day use.

Everything else lives in the braess/ package — you shouldn't need to open
those files unless you're changing the underlying methodology.

Usage:
    python run_analysis.py
"""
from braess import run_braess_analysis

if __name__ == "__main__":
    run_braess_analysis(
        point=(12.9352, 77.6245),    # <-- lat/lon of the area (Koramangala shown)
        dist_m=1500,                  # <-- radius in metres around that point
        use_synthetic=False,           # <-- False = real OSM data, True = synthetic test city
        output_dir=r"C:\Users\OMEN\Desktop\brasses\koramangala",  # <-- where results go
        total_demand=8000,             # <-- background vehicle-trips (tune per area)
        motif_demand=0,                  # <-- leave at 0 for real cities
    )

    # ── Other areas — uncomment one block at a time, or run this file
    #    multiple times with the block you want active ────────────────────

    ##Whitefield, Bengaluru
    # run_braess_analysis(
    #     point=(12.9698, 77.7500),
    #     dist_m=1500,
    #     use_synthetic=False,
    #     output_dir=r"C:\Users\OMEN\Desktop\brasses\whitefield",
    #     total_demand=8000,
    #     motif_demand=0,
    # )

    # # Lajpat Nagar, Delhi
    # run_braess_analysis(
    #     point=(28.5677, 77.2433),
    #     dist_m=1500,
    #     use_synthetic=False,
    #     output_dir=r"C:\Users\OMEN\Desktop\brasses\lajpat_nagar",
    #     total_demand=8000,
    #     motif_demand=0,
    # )

    # Synthetic test city (no internet needed, has known ground truth)

    # run_braess_analysis(
    #     use_synthetic=True,
    #     grid_rows=12, grid_cols=12,
    #     output_dir=r"C:\Users\OMEN\Desktop\brasses\synthetic_test",
    #     total_demand=14000,
    #     motif_demand=1000,
    # )
