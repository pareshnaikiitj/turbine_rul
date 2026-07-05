"""Configuration settings for the turbine RUL prediction workflow."""

CONFIG = {
    # Active parameters (paper-based RPM + Temperature)
    "input_features": ["rpm", "temperature"],
    "target": "rul",

    # Data paths
    "journal_data_path": "data/raw/journal_paper_turbine_data.csv",
    "processed_path": "data/processed/features.csv",
    "predictions_path": "data/processed/latest_unit_predictions.csv",
    "test_size": 0.2,
    "random_state": 42,

    # Healthy blade operating limits (from paper-based reference)
    "healthy_ranges": {
        "rpm": {"min": 5500, "max": 6500, "nominal": 6000},
        "temperature": {"min": 900, "max": 1000, "nominal": 1000},
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
}
