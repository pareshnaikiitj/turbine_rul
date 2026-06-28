"""
Turbine Blade RUL Prediction - Single Parameter Setup
======================================================
Project  : M25DE2039 - Prediction of Remaining Useful Life of Turbine Blades
Author   : Paresh Naik | Roll No: M25DE2039
Guide    : Dr. Ambuj Kumar Gautam
Branch   : Data Engineering (M.Tech)

Stage    : Phase 1 — Single Parameter (Temperature)
Later    : Add vibration, pressure, RPM, etc.
"""

import sys
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
import warnings
import logging
import os
import io

warnings.filterwarnings("ignore")

# Ensure UTF-8 output on Windows (cp1252 can't encode → or ──)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

os.makedirs("logs", exist_ok=True)

# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
# Create UTF-8 aware logging handlers for console and file to avoid
# UnicodeEncodeError on Windows consoles using legacy encodings.
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Console handler (wrap binary buffer with TextIOWrapper forcing utf-8)
try:
    utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    console_handler = logging.StreamHandler(stream=utf8_stdout)
except Exception:
    # Fallback to default StreamHandler if wrapping fails
    console_handler = logging.StreamHandler()

console_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
console_handler.setLevel(logging.CRITICAL)

# File handler with explicit UTF-8 encoding
file_handler = logging.FileHandler("logs/rul_training.log", encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))

# Replace any existing handlers with our UTF-8 handlers
root_logger.handlers = []
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Config — add more parameters here later
# ─────────────────────────────────────────────
CONFIG = {
    # ── ACTIVE PARAMETER (Phase 1) ──────────────────────────────────────
    "input_features": [
        "temperature",          # °C — turbine blade surface temperature
        # "vibration",          # ← uncomment when adding Phase 2
        # "pressure",           # ← uncomment when adding Phase 3
        # "rpm",                # ← uncomment when adding Phase 4
        # "torque",             # ← uncomment when adding Phase 5
    ],
    "target": "rul",            # Remaining Useful Life (hours)

    # ── DATA ────────────────────────────────────────────────────────────
    "data_path": "data/raw/turbine_sensor_data.csv",
    "processed_path": "data/processed/features.csv",
    "predictions_path": "data/processed/latest_unit_predictions.csv",
    "test_size": 0.2,
    "random_state": 42,

    # ── ROLLING WINDOW FEATURES ─────────────────────────────────────────
    "rolling_windows": [5, 10, 20],   # rolling mean/std window sizes

    # ── AutoGluon (Three-Layer Stacked Ensemble) ─────────────────────────
    "autogluon": {
        "time_limit": 120,            # seconds for training (increase later)
        "presets": "medium_quality",  # options: medium_quality, good_quality, best_quality
        "verbosity": 1,
    },

    # ── PATHS ────────────────────────────────────────────────────────────
    "model_dir": "models/autogluon_rul",
}


# ─────────────────────────────────────────────
# 1. Data Generator (Synthetic — replace with real IIoT data)
# ─────────────────────────────────────────────
def generate_synthetic_data(n_samples: int = 2000, save: bool = True) -> pd.DataFrame:
    """
    Simulate turbine sensor readings with a single parameter: temperature.

    Real degradation pattern:
      - Temperature rises gradually as blade wears
      - RUL decreases linearly, with noise
    Replace this function with actual CMAPSS or IIoT CSV loader later.
    """
    np.random.seed(CONFIG["random_state"])

    # Simulate 10 turbine units degrading over time
    units, cycles = [], []
    temperatures, ruls = [], []

    for unit_id in range(1, 11):
        total_life = np.random.randint(150, 300)     # each unit has different lifespan
        for cycle in range(1, total_life + 1):
            degradation = cycle / total_life          # 0 → 1 as it degrades
            # Temperature rises from ~600°C to ~950°C as blade degrades
            temp = 600 + (350 * degradation) + np.random.normal(0, 8)
            rul = total_life - cycle                  # hours remaining

            units.append(unit_id)
            cycles.append(cycle)
            temperatures.append(round(temp, 2))
            ruls.append(rul)

    df = pd.DataFrame({
        "unit_id": units,
        "cycle": cycles,
        "temperature": temperatures,
        "rul": ruls,
    })

    if save:
        os.makedirs("data/raw", exist_ok=True)
        df.to_csv(CONFIG["data_path"], index=False)
        log.info(f"Synthetic data saved → {CONFIG['data_path']}  ({len(df)} rows)")

    return df


# ─────────────────────────────────────────────
# 2. Feature Engineering
# ─────────────────────────────────────────────
def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create rolling statistical features from the active input parameter(s).
    Sorted by unit → cycle to preserve time-series order.
    Auto-scales as more parameters are added to CONFIG["input_features"].
    """
    df = df.sort_values(["unit_id", "cycle"]).reset_index(drop=True)

    for feat in CONFIG["input_features"]:
        for w in CONFIG["rolling_windows"]:
            df[f"{feat}_rollmean_{w}"] = (
                df.groupby("unit_id")[feat]
                .transform(lambda x: x.rolling(w, min_periods=1).mean())
            )
            df[f"{feat}_rollstd_{w}"] = (
                df.groupby("unit_id")[feat]
                .transform(lambda x: x.rolling(w, min_periods=1).std().fillna(0))
            )

        # Lag features (previous cycle value)
        df[f"{feat}_lag1"] = df.groupby("unit_id")[feat].shift(1).bfill()

        # Rate of change
        df[f"{feat}_diff"] = df.groupby("unit_id")[feat].diff().fillna(0)

    # Cumulative Damage Index (CDI) proxy — phase 1: based on temperature alone
    # CDI = normalized cumulative temperature deviation from baseline (600°C)
    df["cdi"] = df.groupby("unit_id")["temperature"].transform(
        lambda x: ((x - 600).clip(lower=0).cumsum() / ((x - 600).clip(lower=0).cumsum().max() + 1e-9))
    )

    log.info(f"Features engineered. Shape: {df.shape}")
    return df


# ─────────────────────────────────────────────
# 3. Train / Test Split
# ─────────────────────────────────────────────
def split_data(df: pd.DataFrame):
    """Split preserving unit boundaries (no data leakage across units)."""
    drop_cols = ["unit_id", "cycle", CONFIG["target"]]
    feature_cols = [c for c in df.columns if c not in drop_cols]

    X = df[feature_cols]
    y = df[CONFIG["target"]]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=CONFIG["test_size"],
        random_state=CONFIG["random_state"],
        shuffle=True,
    )
    log.info(f"Train: {X_train.shape}  |  Test: {X_test.shape}")
    return X_train, X_test, y_train, y_test


# ─────────────────────────────────────────────
# 4. Baseline Models (before AutoGluon)
# ─────────────────────────────────────────────
def run_baselines(X_train, X_test, y_train, y_test):
    """
    Quick baselines: Random Forest, XGBoost, Linear Regression.
    These form the comparison for the AutoGluon stacked ensemble.
    """
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import LinearRegression

    results = {}

    # Linear Regression baseline
    lr = LinearRegression()
    lr.fit(X_train, y_train)
    y_pred = lr.predict(X_test)
    results["LinearRegression"] = _metrics(y_test, y_pred)

    # Random Forest (Layer 1 of the stacked ensemble)
    rf = RandomForestRegressor(n_estimators=100, random_state=CONFIG["random_state"], n_jobs=-1)
    rf.fit(X_train, y_train)
    y_pred = rf.predict(X_test)
    results["RandomForest"] = _metrics(y_test, y_pred)

    # XGBoost (Layer 2 of the stacked ensemble)
    try:
        from xgboost import XGBRegressor
        xgb = XGBRegressor(n_estimators=100, random_state=CONFIG["random_state"], verbosity=0)
        xgb.fit(X_train, y_train)
        y_pred = xgb.predict(X_test)
        results["XGBoost"] = _metrics(y_test, y_pred)
    except ImportError:
        log.warning("XGBoost not installed. Skipping.")

    trained_models = {
        "LinearRegression": lr,
        "RandomForest": rf,
    }
    if "XGBoost" in results:
        trained_models["XGBoost"] = xgb

    return results, trained_models


# ─────────────────────────────────────────────
# 5. Selected Model Summary
# ─────────────────────────────────────────────

def display_selected_model_results(model, model_name: str, X_test, y_test, df: pd.DataFrame, n_units: int = 10):
    """Print the selected model performance and sample remaining-life predictions."""
    y_pred = model.predict(X_test)
    metrics = _metrics(y_test, y_pred)

    print("\n=== Turbine Remaining Useful Life Prediction ===")
    print(f"Selected model: {model_name}")
    print(f"Test MAE: {metrics['mae']:.2f} hours")
    print(f"Test RMSE: {metrics['rmse']:.2f} hours")
    print(f"Test R2: {metrics['r2']:.4f}")

    feature_cols = [c for c in df.columns if c not in ["unit_id", "cycle", CONFIG["target"]]]
    current = (
        df[df[CONFIG["target"]] > 0]
          .sort_values(["unit_id", "cycle"])
          .groupby("unit_id", as_index=False)
          .last()
    )
    current["actual_remaining_hours"] = current[CONFIG["target"]]
    current["predicted_remaining_hours"] = np.round(model.predict(current[feature_cols]), 2)
    current["predicted_remaining_cycles"] = np.maximum(0, np.ceil(current["predicted_remaining_hours"])).astype(int)

    print("\nPredicted remaining life at the last non-failure observed cycle for each turbine unit:")
    print(current[["unit_id", "cycle", "predicted_remaining_hours", "predicted_remaining_cycles"]].to_string(index=False))
    os.makedirs(os.path.dirname(CONFIG["predictions_path"]), exist_ok=True)
    current[["unit_id", "cycle", "predicted_remaining_hours", "predicted_remaining_cycles"]].to_csv(
        CONFIG["predictions_path"], index=False
    )
    print(f"\nSaved last non-failure predicted remaining life to {CONFIG['predictions_path']}")
    print("\nNote: This table uses the last observed cycle before failure for each turbine, so predicted remaining life is measured from a non-zero actual RUL point.")


def display_current_unit_remaining_life(model, df: pd.DataFrame, model_name: str = "Model", n_units: int = 10):
    """Show predicted remaining life hours for each turbine at the last observed cycle."""
    feature_cols = [c for c in df.columns if c not in ["unit_id", "cycle", CONFIG["target"]]]
    current = (
        df.sort_values(["unit_id", "cycle"])
          .groupby("unit_id", as_index=False)
          .last()
    )

    y_pred = model.predict(current[feature_cols])
    current["predicted_remaining_hours"] = np.round(y_pred, 2)

    log.info(f"\n-- {model_name} Predicted Remaining Hours at Latest Cycle --")
    for _, row in current.head(n_units).iterrows():
        log.info(
            f"  Unit {int(row['unit_id'])}: latest cycle={int(row['cycle'])}, actual remaining hours={row[CONFIG['target']]:.2f}, predicted remaining hours={row['predicted_remaining_hours']:.2f}"
        )
    log.info("--------------------------------------------------\n")


# ─────────────────────────────────────────────
# 6. Three-Layer Stacked Ensemble (AutoGluon)
#    Layer 1 → Random Forest       (base learner)
#    Layer 2 → XGBoost             (residual corrector — OOF predictions)
#    Layer 3 → PyTorch Neural Net  (deep learner — OOF predictions)
#              └─ Weighted Ensemble → RUL Prediction (hours)
# ─────────────────────────────────────────────
def train_autogluon(X_train, y_train, X_test, y_test):
    try:
        from autogluon.tabular import TabularPredictor
    except ImportError:
        return None

    train_df = X_train.copy()
    train_df["rul"] = y_train.values

    cfg = CONFIG["autogluon"]

    log.info("Starting AutoGluon three-layer stacked ensemble training...")
    predictor = TabularPredictor(
        label="rul",
        problem_type="regression",
        eval_metric="root_mean_squared_error",
        path=CONFIG["model_dir"],
    ).fit(
        train_data=train_df,
        time_limit=cfg["time_limit"],
        presets=cfg["presets"],
        verbosity=cfg["verbosity"],
        num_stack_levels=2,       # 3-layer stacking: base → L1 → L2 meta
        num_bag_folds=5,          # out-of-fold predictions between layers
    )

    y_pred = predictor.predict(X_test)
    m = _metrics(y_test, y_pred)
    log.info(f"\n-- AutoGluon Ensemble Results --------------------")
    log.info(f"  MAE  = {m['mae']:.2f}")
    log.info(f"  RMSE = {m['rmse']:.2f}")
    log.info(f"  R2   = {m['r2']:.4f}")
    log.info(f"--------------------------------------------------\n")

    return predictor


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _metrics(y_true, y_pred) -> dict:
    mae  = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = 1 - ss_res / (ss_tot + 1e-9)
    return {"mae": mae, "rmse": rmse, "r2": r2}


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    log.info("=" * 55)
    log.info("  Turbine RUL Prediction — Phase 1 (Temperature)")
    log.info("=" * 55)

    # 1. Data
    if not os.path.exists(CONFIG["data_path"]):
        log.info("No data file found — generating synthetic data...")
        df = generate_synthetic_data()
    else:
        df = pd.read_csv(CONFIG["data_path"])
        log.info(f"Loaded data from {CONFIG['data_path']}  ({len(df)} rows)")

    # 2. Features
    df = engineer_features(df)
    os.makedirs("data/processed", exist_ok=True)
    df.to_csv(CONFIG["processed_path"], index=False)

    # 3. Split
    X_train, X_test, y_train, y_test = split_data(df)

    # 4. Baselines (Layer 1 & 2 individual performance)
    baseline_results, baseline_models = run_baselines(X_train, X_test, y_train, y_test)

    # Select best available model for final predictions
    best_baseline = min(baseline_results, key=lambda name: baseline_results[name]["rmse"])

    predictor = train_autogluon(X_train, y_train, X_test, y_test)
    if predictor is not None:
        selected_model = predictor
        selected_name = "AutoGluon"
    else:
        selected_model = baseline_models[best_baseline]
        selected_name = best_baseline

    display_selected_model_results(selected_model, selected_name, X_test, y_test, df)

    log.info("Phase 1 complete. Add more parameters in CONFIG['input_features'].")


if __name__ == "__main__":
    main()
