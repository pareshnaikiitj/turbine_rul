"""Configuration settings for the turbine RUL prediction workflow."""

CONFIG = {
    # Active parameters (paper-based RPM + Temperature). Vibration and
    # pressure have been removed for now — Phase 1 scope only.
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
    # "loading" bounds added so the scenario table can label loading into
    # Low/Medium/High bands, same as rpm and temperature.
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
        # Thermal stress is now the only secondary multiplier on damage.
        "thermal_stress_weight": 0.35,
    },

    # Cumulative damage index at which a blade is considered failed
    # (Palmgren-Miner: sum(n_i / N_fi) >= failure_threshold).
    "failure_threshold": 0.85,

    # Health Score (100 -> new, 0 -> failed) at/below which status becomes
    # Critical, independent of the raw damage index check above.
    "health_threshold": 25,

    # Health score band for "Warning" status (Warning: health_threshold 
    # health <= warning_threshold; Healthy: health > warning_threshold).
    "warning_threshold": 60,

    # RPM operating scenarios simulated for exactly one hour each.
    "scenario_rpms": [3000, 4000, 5000, 6000],

    # Number of independent turbine units simulated, each with its own
    # noise seed / wear history / degradation trend.
    "num_scenario_units": 8,

    # Plot output directory
    "plots_dir": "plots",
}