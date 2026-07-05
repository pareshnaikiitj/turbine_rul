"""
Turbine Blade RUL Prediction - Single Parameter Setup
======================================================
Project  : M25DE2039 - Prediction of Remaining Useful Life of Turbine Blades
Author   : Paresh Naik | Roll No: M25DE2039
Guide    : Dr. Ambuj Kumar Gautam
Branch   : Data Engineering (M.Tech)

Stage    : Phase 1 — Single Parameter (RPM,Temperature)
Later    : Add vibration, pressure, etc.
"""

import sys
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
import warnings
import logging
import os
import io
import time
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import contextlib

from config import CONFIG

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
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

file_handler = logging.FileHandler("logs/rul_training.log", encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))

root_logger.handlers = []
root_logger.addHandler(file_handler)

log = logging.getLogger(__name__)

# Reduce console/noise from noisy third-party libraries; keep logs only in the file handler above.
logging.captureWarnings(True)
for noisy in ("autogluon", "lightgbm", "xgboost", "ray", "fastai", "matplotlib"):
    nl = logging.getLogger(noisy)
    nl.handlers = []
    nl.setLevel(logging.WARNING)
    nl.propagate = False


# Fresh random seed for every execution so output changes each run.
RUN_SEED = int(time.time_ns() % (2**32 - 1))
CONFIG["random_state"] = RUN_SEED


# ─────────────────────────────────────────────
# 1. Load paper-based turbine data
# ─────────────────────────────────────────────
def build_paper_dataset() -> pd.DataFrame:
    """
    Build a journal-paper-based turbine dataset from the reported operating points
    and healthy blade ranges in the cited paper.
    """
    healthy = CONFIG["healthy_ranges"]
    paper = CONFIG["source_paper"]

    rng = np.random.default_rng(CONFIG["random_state"])
    cases = [
        {"unit_id": 1, "rpm": paper["reported_rpm"], "temp_start": 900, "temp_end": 1000, "life": 120},
        {"unit_id": 2, "rpm": 6200, "temp_start": 910, "temp_end": 1000, "life": 110},
        {"unit_id": 3, "rpm": 5800, "temp_start": 900, "temp_end": 970, "life": 130},
        {"unit_id": 4, "rpm": 6500, "temp_start": 920, "temp_end": 1000, "life": 100},
        {"unit_id": 5, "rpm": 5500, "temp_start": 900, "temp_end": 960, "life": 140},
        {"unit_id": 6, "rpm": 6000, "temp_start": 940, "temp_end": 1000, "life": 90},
        {"unit_id": 7, "rpm": 6100, "temp_start": 930, "temp_end": 995, "life": 115},
        {"unit_id": 8, "rpm": 6300, "temp_start": 950, "temp_end": 1000, "life": 105},
    ]

    rows = []
    for case in cases:
        unit_id = case["unit_id"]
        life = case["life"]
        for cycle in range(1, life + 1):
            degradation = cycle / life
            rpm_noise = rng.normal(0, 35)
            rpm = float(np.clip(case["rpm"] + rpm_noise, healthy["rpm"]["min"], healthy["rpm"]["max"]))
            temperature_noise = rng.normal(0, 2.5)
            temperature = case["temp_start"] + (case["temp_end"] - case["temp_start"]) * degradation + temperature_noise
            temperature = float(np.clip(temperature, healthy["temperature"]["min"], healthy["temperature"]["max"]))
            rul = max(0, life - cycle)
            rows.append({
                "unit_id": unit_id,
                "cycle": cycle,
                "rpm": round(rpm, 2),
                "temperature": round(temperature, 2),
                "rul": int(rul),
            })

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(CONFIG["journal_data_path"]), exist_ok=True)
    df.to_csv(CONFIG["journal_data_path"], index=False)
    log.info(f"Built journal-paper turbine dataset at {CONFIG['journal_data_path']} ({len(df)} rows)")
    return df


def load_paper_dataset() -> pd.DataFrame:
    """Always rebuild the dataset so each run produces different turbine values."""
    return build_paper_dataset()


# ─────────────────────────────────────────────
# 2. Feature Engineering
# ─────────────────────────────────────────────
def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create rolling statistical features from the active input parameter(s).
    Sorted by unit → cycle to preserve time-series order.
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

        df[f"{feat}_lag1"] = df.groupby("unit_id")[feat].shift(1).bfill()
        df[f"{feat}_diff"] = df.groupby("unit_id")[feat].diff().fillna(0)

    baseline_temp = CONFIG["healthy_ranges"]["temperature"]["nominal"]
    baseline_rpm = CONFIG["healthy_ranges"]["rpm"]["nominal"]
    df["cdi"] = (
        df.groupby("unit_id")["temperature"].transform(lambda x: ((x - baseline_temp).clip(lower=0).cumsum()))
        + df.groupby("unit_id")["rpm"].transform(lambda x: ((x - baseline_rpm).abs().cumsum()))
    )
    df["cdi"] = df["cdi"] / (df["cdi"].max() + 1e-9)

    log.info(f"Features engineered. Shape: {df.shape}")
    return df


# ─────────────────────────────────────────────
# 3. Train / Test Split (by whole unit — no leakage)
# ─────────────────────────────────────────────
def split_data(df: pd.DataFrame):
    """
    Split by whole turbine unit_id, not by row. This keeps every cycle of a
    given unit entirely in either train or test, preventing the model from
    seeing a turbine's other cycles during training.
    """
    drop_cols = ["unit_id", "cycle", CONFIG["target"]]
    feature_cols = [c for c in df.columns if c not in drop_cols]

    unit_ids = df["unit_id"].unique()
    rng = np.random.default_rng(CONFIG["random_state"])
    rng.shuffle(unit_ids)

    n_test_units = max(1, int(round(len(unit_ids) * CONFIG["test_size"])))
    test_units = set(unit_ids[:n_test_units])
    train_units = set(unit_ids[n_test_units:])

    train_df = df[df["unit_id"].isin(train_units)].reset_index(drop=True)
    test_df = df[df["unit_id"].isin(test_units)].reset_index(drop=True)

    X_train, y_train = train_df[feature_cols], train_df[CONFIG["target"]]
    X_test, y_test = test_df[feature_cols], test_df[CONFIG["target"]]

    log.info(f"Train units: {sorted(train_units)}  ({X_train.shape})")
    log.info(f"Test units:  {sorted(test_units)}  ({X_test.shape})")
    return X_train, X_test, y_train, y_test


# ─────────────────────────────────────────────
# 4. Final Model — AutoGluon Three-Layer Stacked Ensemble
#    Layer 1 → Random Forest       (base learner)
#    Layer 2 → XGBoost             (residual corrector — OOF predictions)
#    Layer 3 → PyTorch Neural Net  (deep learner — OOF predictions)
#              └─ Weighted Ensemble → RUL Prediction (hours)
#
#    This single model produces the "Turbine Remaining Useful Life
#    Prediction" result. 
# ─────────────────────────────────────────────
def train_final_model(X_train, y_train, X_test, y_test):
    """Returns (model_name, predict_fn, metrics)."""
    # Try importing and running AutoGluon inside a suppression context so
    # its stdout/stderr prints don't appear in the console.
    try:
        with open(os.devnull, "w") as devnull:
            with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
                from autogluon.tabular import TabularPredictor

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
    except ImportError:
        from sklearn.ensemble import RandomForestRegressor

        rf = RandomForestRegressor(n_estimators=200, random_state=CONFIG["random_state"], n_jobs=-1)
        rf.fit(X_train, y_train)
        y_pred = rf.predict(X_test)
        metrics = _metrics(y_test, y_pred)
        return "RandomForest", rf.predict, metrics
    except Exception:
        # If AutoGluon fails for any reason inside the suppressed block,
        # log the exception and fallback to RandomForest.
        log.exception("AutoGluon training failed; falling back to RandomForest")
        from sklearn.ensemble import RandomForestRegressor

        rf = RandomForestRegressor(n_estimators=200, random_state=CONFIG["random_state"], n_jobs=-1)
        rf.fit(X_train, y_train)
        y_pred = rf.predict(X_test)
        metrics = _metrics(y_test, y_pred)
        return "RandomForest", rf.predict, metrics

    train_df = X_train.copy()
    train_df["rul"] = y_train.values
    cfg = CONFIG["autogluon"]

    log.info("Starting AutoGluon three-layer stacked ensemble training...")
    # TabularPredictor emits many prints/warnings to stdout/stderr; suppress them
    # so the console remains quiet and all logs go to the logfile.
    try:
        with open(os.devnull, "w") as devnull:
            with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
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
    except Exception:
        # If AutoGluon fails for any reason, fallback to RandomForest
        log.exception("AutoGluon training failed; falling back to RandomForest")
        from sklearn.ensemble import RandomForestRegressor

        rf = RandomForestRegressor(n_estimators=200, random_state=CONFIG["random_state"], n_jobs=-1)
        rf.fit(X_train, y_train)
        y_pred = rf.predict(X_test)
        metrics = _metrics(y_test, y_pred)
        return "RandomForest", rf.predict, metrics

    y_pred = np.asarray(predictor.predict(X_test))
    metrics = _metrics(y_test, y_pred)

    def predict_fn(X):
        return np.asarray(predictor.predict(X))

    return "AutoGluon (3-Layer Stacked Ensemble)", predict_fn, metrics


# ─────────────────────────────────────────────
# 5. Display + Example Predictions (single model, single output column)
# ─────────────────────────────────────────────
def display_final_model_results(model_name: str, metrics: dict):
    """Single combined block — replaces the old separate LR/RF/XGBoost prints."""
    print("\n=== Turbine Remaining Useful Life Prediction ===")
    print(f"Selected model: {model_name}")
    print(f"Test MAE: {metrics['mae']:.2f} hours")
    print(f"Test RMSE: {metrics['rmse']:.2f} hours")
    print(f"Test R2: {metrics['r2']:.4f}")


def build_simple_trend_models(df: pd.DataFrame):
    """Train lightweight trend models for RPM and temperature so the output can show predicted values."""
    from sklearn.linear_model import LinearRegression

    feature_df = df[["unit_id", "cycle", "rpm", "temperature"]].copy()
    rpm_model = LinearRegression()
    temp_model = LinearRegression()

    rpm_model.fit(feature_df[["unit_id", "cycle"]], feature_df["rpm"])
    temp_model.fit(feature_df[["unit_id", "cycle"]], feature_df["temperature"])
    return rpm_model, temp_model


def predict_for_operating_conditions(predict_fn, feature_cols, df: pd.DataFrame):
    """Predict RUL for several concrete turbine examples using the single final model."""
    healthy = CONFIG["healthy_ranges"]

    example_rows = df.head(10).copy()
    example_rows = example_rows[["unit_id", "cycle", "rpm", "temperature", "rul"]].copy()
    example_rows = example_rows.rename(columns={"rul": "actual_rul_hours"})

    rpm_model, temp_model = build_simple_trend_models(df)

    rows = []
    for _, row in example_rows.iterrows():
        case_df = pd.DataFrame([
            {
                "unit_id": int(row["unit_id"]),
                "cycle": int(row["cycle"]),
                "rpm": float(row["rpm"]),
                "temperature": float(row["temperature"]),
                "rul": 0,
            }
        ])
        case_df = engineer_features(case_df)
        case_df = case_df[feature_cols].fillna(0)

        pred_rul = float(predict_fn(case_df[feature_cols])[0])

        pred_rpm = float(rpm_model.predict([[int(row["unit_id"]), int(row["cycle"])]])[0])
        pred_temp = float(temp_model.predict([[int(row["unit_id"]), int(row["cycle"])]])[0])

        rows.append((
            int(row["unit_id"]),
            int(row["cycle"]),
            float(row["rpm"]),
            round(pred_rpm, 2),
            float(row["temperature"]),
            round(pred_temp, 2),
            float(row["actual_rul_hours"]),
            round(pred_rul, 2),
        ))

    out = pd.DataFrame(
        rows,
        columns=[
            "unit_id",
            "cycle",
            "actual_rpm",
            "predicted_rpm",
            "actual_temperature",
            "predicted_temperature",
            "actual_rul_hours",
            "predicted_rul_hours",
        ],
    )
    print("\n=== Example Turbine RUL Predictions ===")
    print(f"Paper URL: {CONFIG['source_paper']['url']}")
    print(
        f"Healthy range → RPM: {healthy['rpm']['min']} to {healthy['rpm']['max']} | "
        f"Temperature: {healthy['temperature']['min']} to {healthy['temperature']['max']} K"
    )
    print(out.to_string(index=False))

    print("\nGenerating graphical pattern for the turbine examples...")
    plot_df = out.head(8).copy()
    if not plot_df.empty:
        fig, axes = plt.subplots(2, 1, figsize=(8, 6), sharex=True)

        ax1, ax2 = axes
        ax1.plot(plot_df["cycle"], plot_df["actual_rpm"], marker="^", linewidth=1.8, color="tab:green", label="Actual RPM")
        ax1_t = ax1.twinx()
        ax1_t.plot(plot_df["cycle"], plot_df["predicted_rul_hours"], marker="s", linewidth=1.8, color="tab:red", label="Predicted RUL")
        ax1.set_title("Turbine RPM and Predicted RUL")
        ax1.set_ylabel("RPM")
        ax1_t.set_ylabel("Predicted RUL")
        ax1.grid(True, alpha=0.3)

        ax2.plot(plot_df["cycle"], plot_df["actual_temperature"], marker="o", linewidth=1.8, color="tab:blue", label="Actual Temperature")
        ax2_t = ax2.twinx()
        ax2_t.plot(plot_df["cycle"], plot_df["predicted_rul_hours"], marker="s", linewidth=1.8, color="tab:red", label="Predicted RUL")
        ax2.set_title("Turbine Temperature and Predicted RUL")
        ax2.set_xlabel("Cycle")
        ax2.set_ylabel("Temperature")
        ax2_t.set_ylabel("Predicted RUL")
        ax2.grid(True, alpha=0.3)

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax1_t.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right")

        lines1, labels1 = ax2.get_legend_handles_labels()
        lines2, labels2 = ax2_t.get_legend_handles_labels()
        ax2.legend(lines1 + lines2, labels1 + labels2, loc="upper right")

        fig.tight_layout()
        plot_path = "data/processed/turbine_trend_plot.png"
        os.makedirs(os.path.dirname(plot_path), exist_ok=True)
        fig.savefig(plot_path, dpi=150)
        plt.close(fig)
        print(f"Saved graphical pattern to {plot_path}")

        # Also generate a degradation (CDI) plot for the same example units
        try:
            deg_plot_path = "data/processed/turbine_degradation_plot.png"
            units = plot_df["unit_id"].unique()
            fig2, ax = plt.subplots(figsize=(8, 3 + len(units) * 0.5))
            for uid in units:
                unit_df = df[df["unit_id"] == uid]
                ax.plot(unit_df["cycle"], unit_df["cdi"], marker="o", linewidth=1.5, label=f"Unit {uid}")
            ax.set_title("Cumulative Degradation Index (CDI) by Cycle")
            ax.set_xlabel("Cycle")
            ax.set_ylabel("CDI (normalized)")
            ax.grid(True, alpha=0.3)
            ax.legend(loc="upper right")
            fig2.tight_layout()
            fig2.savefig(deg_plot_path, dpi=150)
            plt.close(fig2)
            print(f"Saved degradation pattern to {deg_plot_path}")
        except Exception:
            log.exception("Failed to generate degradation plot")

        # Try opening the images on desktop (Windows `os.startfile`), ignore failures
        try:
            if os.name == "nt":
                try:
                    os.startfile(plot_path)
                except Exception:
                    log.debug("Could not open trend plot automatically")
                try:
                    os.startfile(deg_plot_path)
                except Exception:
                    log.debug("Could not open degradation plot automatically")
        except Exception:
            log.debug("Automatic image open skipped or failed")

    return out


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _metrics(y_true, y_pred) -> dict:
    mae = mean_absolute_error(y_true, y_pred)
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
    log.info("  Turbine RUL Prediction — Paper-based RPM + Temperature")
    log.info("=" * 55)

    healthy = CONFIG["healthy_ranges"]
    paper = CONFIG["source_paper"]
    log.info(f"Source paper: {paper['title']} ({paper['journal']})")
    log.info(f"Run seed: {RUN_SEED}")
    log.info(
        f"Healthy blade limits → RPM {healthy['rpm']['min']}-{healthy['rpm']['max']} (nominal {healthy['rpm']['nominal']}) | "
        f"Temperature {healthy['temperature']['min']}-{healthy['temperature']['max']} K "
        f"({healthy['temperature']['min']-273.15:.0f}°C-{healthy['temperature']['max']-273.15:.0f}°C; nominal {healthy['temperature']['nominal']-273.15:.0f}°C)"
    )
    log.info(
        f"Reported paper operating point → RPM {paper['reported_rpm']} | Temperature {paper['reported_temperature_k']} K "
        f"({paper['reported_temperature_c']:.2f}°C)"
    )
    log.info(f"Paper URL: {paper['url']}")

    # 1. Data
    df = load_paper_dataset()

    # 2. Features
    df = engineer_features(df)
    os.makedirs("data/processed", exist_ok=True)
    df.to_csv(CONFIG["processed_path"], index=False)

    # 3. Split — by whole unit, no leakage
    X_train, X_test, y_train, y_test = split_data(df)

    # 4. Train the single final model (AutoGluon, or RandomForest fallback)
    model_name, predict_fn, metrics = train_final_model(X_train, y_train, X_test, y_test)

    # 5. Combined display — one block, one model
    display_final_model_results(model_name, metrics)

    feature_cols = list(X_train.columns)
    predict_for_operating_conditions(predict_fn, feature_cols, df)

    log.info("Paper-based RPM + temperature RUL training complete.")


if __name__ == "__main__":
    main()