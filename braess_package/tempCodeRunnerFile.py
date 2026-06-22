run_braess_analysis(
        point=(12.9352, 77.6245),    # <-- lat/lon of the area (Koramangala shown)
        dist_m=1500,                  # <-- radius in metres around that point
        use_synthetic=False,           # <-- False = real OSM data, True = synthetic test city
        output_dir=r"C:\Users\OMEN\Desktop\brasses_package\koramangala",  # <-- where results go
        total_demand=8000,             # <-- background vehicle-trips (tune per area)
        motif_demand=0,                  # <-- leave at 0 for real cities
    )