"""Configuration settings for the turbine RUL prediction workflow."""

CONFIG = {
    # Active parameters (paper-based RPM + Temperature + Loading).
    "input_features": ["rpm", "temperature", "loading", "time_hours"],
    "target": "rul",

    # Data paths
    "journal_data_path": "data/raw/journal_paper_turbine_data.csv",
    "processed_path": "data/processed/features.csv",
    "predictions_path": "data/processed/latest_unit_predictions.csv",
    "scenario_table_path": "data/processed/rpm_scenario_table.csv",
    "test_size": 0.2,
    "random_state": 42,

    # Healthy blade operating limits (from paper-based reference).
    "healthy_ranges": {
        "rpm": {"min": 3000, "max": 6000, "nominal": 4500},
        "temperature": {"min": 400, "max": 1000, "nominal": 700},
        "loading": {"min": 0.45, "max": 0.95, "nominal": 0.70},
    },

    # Source paper reference
    "source_paper": {
        "title": "Thermo mechanical analysis of the gas turbine blade",
        "journal": "Manufacturing Technology Today",
        "url": "https://mtt.cmti.res.in/index.php/journal/article/download/142/123/199",
        "reported_rpm": 6000,
        "reported_temperature_k": 1000,
        "reported_temperature_c": 726.85,
    },

    # Rolling window features
    "rolling_windows": [5, 10, 20],

    # AutoGluon settings
    "autogluon": {
        "time_limit": 120,
        "presets": "medium_quality",
        "verbosity": 1,
    },

    # Model paths
    "model_dir": "models/autogluon_rul",

    # ------------------------------------------------------------------
    # Degradation model constants (Basquin's equation + Palmgren-Miner
    # cumulative damage rule + centrifugal stress scaling ~ rpm^2).
    # Vibration-based wear term removed along with the vibration sensor.
    # ------------------------------------------------------------------
    "degradation_model": {
        "basquin_exponent": -0.5,
        "stress_rpm_ref": 6000,
        "fatigue_strength_coefficient": 1.0,
        "life_scale_hours": 140,
        "thermal_stress_weight": 0.35,
    },

    # Cumulative damage index at which a blade is considered failed
    # (Palmgren-Miner: sum(n_i / N_fi) >= failure_threshold).
    "failure_threshold": 0.85,

    # Health Score (100 -> new, 0 -> failed) at/below which status becomes
    # Critical, independent of the raw damage index check above.
    "health_threshold": 25,

    # Health score band for "Warning" status.
    "warning_threshold": 60,

    # RPM operating scenarios simulated for exactly one hour each.
    "scenario_rpms": [3000, 4000, 5000, 6000],

    # Number of independent turbine units simulated.
    "num_scenario_units": 8,

    # Plot output directory
    "plots_dir": "plots",

    # ------------------------------------------------------------------
    # SLMTA15 material S-N (stress-life) fatigue model.
    # Table points are the geometric mean of each cycle range supplied,
    # used as representative (stress, fatigue_life_cycles) pairs for
    # log-linear interpolation (stress vs log10(N)) between them.
    # ------------------------------------------------------------------
    "material_sn_curve": {
        "material": "SLMTA15",
        "stress_life_points": [
            # (stress_MPa, fatigue_life_cycles)  -- using UPPER BOUND of scatter range
            (900, 8.0e4),    # range 2e4 - 8e4
            (850, 2.0e5),    # range 5e4 - 2e5
            (800, 5.0e5),    # range 1e5 - 5e5
            (750, 1.0e6),    # range 3e5 - 1e6
            (700, 4.0e6),    # range 8e5 - 4e6
            (650, 2.0e7),    # range 2e6 - 2e7
            (600, 8.0e7),    # range 8e6 - 8e7
            (500, 1.0e8),    # run-out
        ],
        "build_orientation_fatigue_strength_mpa": {
            "horizontal": 500,   # H-HCF, ~500 MPa @ 1e8 cycles
            "vertical": 600,     # V-HCF, ~600 MPa @ 1e8 cycles
        },
    },

    # Loading (0-1 ratio) is linearly mapped onto this stress range (MPa)
    # to feed the SLMTA15 S-N curve above.
    "stress_range_mpa": {"min": 500, "max": 900},

    # Default number of hours the unit is assumed to have ALREADY operated
    # (using its own real historical data) before evaluating each new RPM
    # scenario going forward. Override per-call if needed.
    "default_used_hours": 15,

    # ------------------------------------------------------------------
    # REAL DATA INGESTION (replaces synthetic build_paper_dataset when a
    # real CSV is supplied). New real data is merged into this persistent
    # store on every run — never overwritten, only appended/deduplicated —
    # so "old data" (previous runs) and "current data" (this run's rows)
    # accumulate continuously instead of being regenerated each time.
    # ------------------------------------------------------------------
    "use_real_data": True,
    "real_data_store_path": "data/raw/turbine_real_data_store.csv",
}