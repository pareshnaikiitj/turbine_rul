"""
Turbine Blade RUL Prediction - 
======================================================
Project  : M25DE2039 - Prediction of Remaining Useful Life of Turbine Blades
Author   : Paresh Naik | Roll No: M25DE2039
Guide    : Dr. Ambuj Kumar Gautam
Branch   : Data Engineering (M.Tech)

Stage    : Phase 1 — Parameters (RPM,Temperature)
Later    : Add vibration, pressure, etc.
"""

import sys
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
import warnings
import logging
import os
import time
import contextlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

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
# 1. Load paper-based turbine data (now with vibration + pressure)
# ─────────────────────────────────────────────
def calculate_loading_and_time(rpm: float, cycle: int, life: int, healthy: dict) -> tuple[float, float]:
    """Create a loading and time signal that rises with RPM so higher rpm shows higher loading."""
    rpm_span = max(1.0, healthy["rpm"]["max"] - healthy["rpm"]["min"])
    rpm_ratio = (rpm - healthy["rpm"]["min"]) / rpm_span
    rpm_ratio = float(np.clip(rpm_ratio, 0.0, 1.0))
    degradation = cycle / max(1, life)
    loading = round(0.45 + 0.45 * rpm_ratio + 0.05 * degradation, 3)
    time_hours = round(cycle * (1.0 + 0.35 * rpm_ratio + 0.05 * degradation), 2)
    return loading, time_hours


def _rpm_ratio(rpm: float, healthy: dict) -> float:
    span = max(1.0, healthy["rpm"]["max"] - healthy["rpm"]["min"])
    return float(np.clip((rpm - healthy["rpm"]["min"]) / span, 0.0, 1.0))


def build_paper_dataset() -> pd.DataFrame:
    """
    Build a journal-paper-based turbine dataset from the reported operating points
    and healthy blade ranges in the cited paper. Now also simulates vibration and
    pressure so the dataset carries the full multi-sensor picture used by the
    RPM-scenario damage/health simulator below.
    """
    healthy = CONFIG["healthy_ranges"]
    paper = CONFIG["source_paper"]

    rng = np.random.default_rng(CONFIG["random_state"])
    cases = [
        {"unit_id": 1, "rpm": paper["reported_rpm"], "temp_start": 500, "temp_end": 900, "life": 120},
        {"unit_id": 2, "rpm": 5200, "temp_start": 520, "temp_end": 920, "life": 110},
        {"unit_id": 3, "rpm": 4800, "temp_start": 480, "temp_end": 880, "life": 130},
        {"unit_id": 4, "rpm": 5600, "temp_start": 540, "temp_end": 940, "life": 100},
        {"unit_id": 5, "rpm": 4200, "temp_start": 450, "temp_end": 860, "life": 140},
        {"unit_id": 6, "rpm": 5000, "temp_start": 560, "temp_end": 900, "life": 90},
        {"unit_id": 7, "rpm": 5400, "temp_start": 530, "temp_end": 910, "life": 115},
        {"unit_id": 8, "rpm": 5800, "temp_start": 550, "temp_end": 950, "life": 105},
    ]

    v_nom, v_max = healthy["vibration"]["nominal"], healthy["vibration"]["max"]
    p_nom = healthy["pressure"]["nominal"]

    rows = []
    for case in cases:
        unit_id = case["unit_id"]
        life = case["life"]
        rpm_ratio_case = _rpm_ratio(case["rpm"], healthy)
        for cycle in range(1, life + 1):
            degradation = cycle / life
            rpm_noise = rng.normal(0, 35)
            rpm = float(np.clip(case["rpm"] + rpm_noise, healthy["rpm"]["min"], healthy["rpm"]["max"]))
            temperature_noise = rng.normal(0, 2.5)
            temperature = case["temp_start"] + (case["temp_end"] - case["temp_start"]) * degradation + temperature_noise
            temperature = float(np.clip(temperature, healthy["temperature"]["min"], healthy["temperature"]["max"]))
            loading, time_hours = calculate_loading_and_time(rpm, cycle, life, healthy)

            # Vibration grows with both RPM level and accumulated degradation
            # (bearing/blade wear), plus stochastic noise.
            vibration = v_nom + (v_max - v_nom) * (0.35 * rpm_ratio_case + 0.55 * degradation)
            vibration += rng.normal(0, 0.08)
            vibration = float(np.clip(vibration, healthy["vibration"]["min"], healthy["vibration"]["max"]))

            # Pressure fluctuates mildly around nominal; slight dip as rpm rises.
            pressure = p_nom - 3.0 * rpm_ratio_case + rng.normal(0, 0.6)
            pressure = float(np.clip(pressure, healthy["pressure"]["min"], healthy["pressure"]["max"]))

            rul = max(0, life - cycle)
            rows.append({
                "unit_id": unit_id,
                "cycle": cycle,
                "rpm": round(rpm, 2),
                "temperature": round(temperature, 2),
                "loading": loading,
                "time_hours": time_hours,
                "vibration": round(vibration, 3),
                "pressure": round(pressure, 2),
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
    Create rolling statistical features from the active input parameter(s),
    plus the new physics-grounded degradation features: RPM stress index,
    thermal stress, bearing-wear index, damage accumulation (Palmgren-Miner
    style), health index, exponential degradation score and normalized
    remaining life. Sorted by unit → cycle to preserve time-series order.
    """
    df = df.sort_values(["unit_id", "cycle"]).reset_index(drop=True)
    healthy = CONFIG["healthy_ranges"]
    deg_cfg = CONFIG["degradation_model"]
    failure_threshold = CONFIG["failure_threshold"]

    # Rolling stats / lag / diff for every active sensor (rpm, temperature,
    # loading, time_hours, vibration, pressure) — unchanged mechanism, now
    # automatically also covers vibration & pressure since they were added
    # to CONFIG["input_features"].
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

    baseline_temp = healthy["temperature"]["nominal"]
    baseline_rpm = healthy["rpm"]["nominal"]
    baseline_vib = healthy["vibration"]["nominal"]

    df["temp_rise"] = df.groupby("unit_id")["temperature"].diff().fillna(0)
    df["loading_rise"] = df.groupby("unit_id")["loading"].diff().fillna(0)
    df["rpm_rise"] = df.groupby("unit_id")["rpm"].diff().fillna(0)
    df["operating_hours"] = df["time_hours"]
    df["running_hours"] = df.groupby("unit_id").cumcount() + 1
    df["cycle_progress"] = df.groupby("unit_id")["cycle"].rank(method="first") / df.groupby("unit_id").size().reindex(df["unit_id"]).to_numpy()
    df["cycle_progress"] = df["cycle_progress"].fillna(0)

    # --- Physics-based degradation features -----------------------------
    # RPM stress index: centrifugal stress scales with rpm^2 (normalized to
    # the reference/nominal rpm from the degradation model config).
    rpm_ref = deg_cfg["stress_rpm_ref"]
    df["rpm_stress_index"] = (df["rpm"] / rpm_ref) ** 2

    # Thermal stress: how far above nominal operating temperature, clipped >= 0.
    t_max = healthy["temperature"]["max"]
    df["thermal_stress"] = ((df["temperature"] - baseline_temp) / max(1.0, (t_max - baseline_temp))).clip(lower=0)

    # Bearing wear index: cumulative vibration energy (sum of vibration^2),
    # normalized within each unit's own run so it stays in [0, 1].
    vib_energy = df.groupby("unit_id")["vibration"].transform(lambda x: (x ** 2).cumsum())
    df["bearing_wear_index"] = df.groupby("unit_id")["unit_id"].transform(
        lambda g: vib_energy.loc[g.index] / (vib_energy.loc[g.index].max() + 1e-9)
    )

    # Per-row damage increment via Basquin's equation + Palmgren-Miner rule,
    # accumulated per unit to give a running damage index in [0, ~1+].
    def _damage_increment_row(rpm, temperature, vibration):
        return compute_hourly_damage_increment(rpm, temperature, vibration, deg_cfg, healthy)[0]

    df["damage_increment"] = [
        _damage_increment_row(r, t, v) for r, t, v in zip(df["rpm"], df["temperature"], df["vibration"])
    ]
    df["damage_index"] = df.groupby("unit_id")["damage_increment"].cumsum()

    # Health index: 100 at new condition, falling to 0 as damage_index -> 1.0.
    df["health_index"] = (100.0 * (1.0 - df["damage_index"].clip(upper=1.0))).clip(lower=0.0)

    # Exponential degradation score: emphasizes the accelerating tail-end
    # of wear (small at low damage, grows quickly as damage_index rises).
    df["exp_degradation_score"] = 1.0 - np.exp(-5.0 * df["damage_index"])

    # Normalized remaining life relative to the configured failure threshold.
    df["normalized_remaining_life"] = (1.0 - df["damage_index"] / failure_threshold).clip(lower=0.0, upper=1.0)

    # Keep the original cumulative degradation index (cdi) for backward
    # compatibility with earlier phase-1 experiments/plots.
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
# 4. Final Model — AutoGluon Three-Layer Stacked Ensemble (unchanged)
#    Layer 1 → Random Forest       (base learner)
#    Layer 2 → XGBoost             (residual corrector — OOF predictions)
#    Layer 3 → PyTorch Neural Net  (deep learner — OOF predictions)
#              └─ Weighted Ensemble → RUL Prediction (hours)
# ─────────────────────────────────────────────
def train_final_model(X_train, y_train, X_test, y_test):
    """Returns (model_name, predict_fn, metrics)."""
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
# 5. Display + Combined Prediction Summary (unchanged)
# ─────────────────────────────────────────────
def display_final_model_results(model_name: str, metrics: dict):
    """Single combined block for model performance."""
    print("\n=== Turbine Remaining Useful Life Prediction ===")
    print(f"Selected model: {model_name}")
    print(f"Test MAE: {metrics['mae']:.2f} hours")
    print(f"Test RMSE: {metrics['rmse']:.2f} hours")
    print(f"Test R2: {metrics['r2']:.4f}")


def predict_for_selected_cycles(predict_fn, feature_cols, df: pd.DataFrame,
                                 unit_ids: list | None = None,
                                 cycles: list | None = None) -> pd.DataFrame:
    """
    Combined table across ALL turbine units: actual sensor values
    + actual vs predicted RUL for specific cycles (e.g. 1, 10, 60, 120).
    """
    if unit_ids is None:
        unit_ids = sorted(df["unit_id"].unique())
    if cycles is None:
        cycles = [1, 10, 60, 120]

    rows = []
    for unit_id in unit_ids:
        unit_df = df[df["unit_id"] == unit_id].sort_values("cycle").reset_index(drop=True)
        if unit_df.empty:
            continue
        max_cycle = int(unit_df["cycle"].max())

        for target_cycle in cycles:
            c = min(target_cycle, max_cycle)
            match_idx = (unit_df["cycle"] - c).abs().idxmin()
            row = unit_df.loc[match_idx]

            case_df = pd.DataFrame([{
                "unit_id": int(row["unit_id"]),
                "cycle": int(row["cycle"]),
                "rpm": float(row["rpm"]),
                "temperature": float(row["temperature"]),
                "loading": float(row["loading"]),
                "time_hours": float(row["time_hours"]),
                "vibration": float(row["vibration"]),
                "pressure": float(row["pressure"]),
                "rul": 0,
            }])
            case_df = engineer_features(case_df)
            case_df = case_df[feature_cols].fillna(0)
            pred_rul = float(predict_fn(case_df[feature_cols])[0])

            rows.append({
                "unit_id": int(row["unit_id"]),
                "cycle": int(row["cycle"]),
                "rpm": round(float(row["rpm"]), 2),
                "temperature": round(float(row["temperature"]), 2),
                "vibration": round(float(row["vibration"]), 3),
                "pressure": round(float(row["pressure"]), 2),
                "loading": round(float(row["loading"]), 3),
                "time_hours": round(float(row["time_hours"]), 2),
                "actual_rul_hours": float(row["rul"]),
                "predicted_rul_hours": round(pred_rul, 2),
            })

    out = pd.DataFrame(rows)
    print("\n=== Turbine RUL Prediction Summary (All Units) ===")
    print(out.to_string(index=False))
    return out


# ─────────────────────────────────────────────
# 6. NEW — Physics-based hourly damage model
#    (Basquin's equation + Palmgren-Miner cumulative damage rule +
#     centrifugal stress ~ rpm^2)
# ─────────────────────────────────────────────
def compute_hourly_damage_increment(rpm: float, temperature: float, vibration: float,
                                     deg_cfg: dict, healthy: dict) -> tuple[float, float, float, float]:
    """
    Returns (damage_increment_per_hour, rpm_stress_index, thermal_stress, vibration_stress).

    Centrifugal stress amplitude is modeled as scaling with rpm^2 (standard
    rotor-dynamics relationship), non-dimensionalized against a reference rpm.
    Basquin's equation (sigma_a = sigma_f' * (2 N_f)^b) is inverted to get the
    number of hours-to-failure N_f at that stress level; 1/N_f is the base
    per-hour damage increment (Palmgren-Miner rule: damage accumulates as
    n_i / N_fi and failure occurs when the sum reaches the failure threshold).
    Thermal stress and vibration (bearing wear precursor) act as secondary
    multipliers on top of the centrifugal-stress-driven base damage rate.
    """
    rpm_ref = deg_cfg["stress_rpm_ref"]
    b = deg_cfg["basquin_exponent"]
    sigma_f = deg_cfg["fatigue_strength_coefficient"]

    life_scale = deg_cfg.get("life_scale_hours", 1.0)
    stress_amp = (rpm / rpm_ref) ** 2  # rpm_stress_index
    ratio = max(stress_amp / sigma_f, 1e-6)
    n_f_hours = life_scale * 0.5 * (ratio ** (1.0 / b))  # Basquin's equation, solved for N_f
    n_f_hours = max(n_f_hours, 1e-3)
    base_damage_per_hour = 1.0 / n_f_hours

    t_max, t_nom = healthy["temperature"]["max"], healthy["temperature"]["nominal"]
    thermal_stress = max(0.0, (temperature - t_nom) / max(1.0, (t_max - t_nom)))

    v_nom, v_max = healthy["vibration"]["nominal"], healthy["vibration"]["max"]
    vibration_stress = max(0.0, (vibration - v_nom) / max(1e-6, (v_max - v_nom)))

    multiplier = 1.0 + deg_cfg["thermal_stress_weight"] * thermal_stress + deg_cfg["vibration_stress_weight"] * vibration_stress
    damage_increment = base_damage_per_hour * multiplier
    return damage_increment, stress_amp, thermal_stress, vibration_stress


def _status_from_health(health_score: float, damage_index: float, cfg: dict) -> str:
    if damage_index >= cfg["failure_threshold"] or health_score <= cfg["health_threshold"]:
        return "Critical"
    if health_score <= cfg["warning_threshold"]:
        return "Warning"
    return "Healthy"


def simulate_one_hour_scenario(unit_id: int, rpm: float, prior_damage_index: float,
                                prior_op_hours: float, rng: np.random.Generator) -> dict:
    """
    Simulate exactly ONE HOUR of operation for a given unit at a given RPM,
    starting from that unit's own current damage/operating-hour state, and
    dynamically generate the resulting sensor readings + damage/health
    outcome. Every call with a fresh rng produces different noise, so no two
    runs (or units) look alike, matching the "no static values" requirement.
    """
    healthy = CONFIG["healthy_ranges"]
    deg_cfg = CONFIG["degradation_model"]
    rpm_ratio = _rpm_ratio(rpm, healthy)

    # Temperature: rises with RPM level and slowly with accumulated
    # operating time (thermal soak), plus stochastic noise.
    t_nom, t_max = healthy["temperature"]["nominal"], healthy["temperature"]["max"]
    temperature = t_nom + (t_max - t_nom) * 0.55 * rpm_ratio + 0.04 * prior_op_hours
    temperature += rng.normal(0, 3.0)
    temperature = float(np.clip(temperature, healthy["temperature"]["min"], healthy["temperature"]["max"]))

    # Vibration: rises with RPM level and with existing accumulated damage
    # (worn blades/bearings vibrate more), plus noise.
    v_nom, v_max = healthy["vibration"]["nominal"], healthy["vibration"]["max"]
    vibration = v_nom + (v_max - v_nom) * (0.4 * rpm_ratio + 0.5 * min(prior_damage_index, 1.0))
    vibration += rng.normal(0, 0.10)
    vibration = float(np.clip(vibration, healthy["vibration"]["min"], healthy["vibration"]["max"]))

    # Pressure: mild fluctuation around nominal, slight dip at high rpm.
    p_nom = healthy["pressure"]["nominal"]
    pressure = p_nom - 3.0 * rpm_ratio + rng.normal(0, 0.5)
    pressure = float(np.clip(pressure, healthy["pressure"]["min"], healthy["pressure"]["max"]))

    # Load / loading factor, consistent with the phase-1 formula.
    loading = round(0.45 + 0.45 * rpm_ratio + 0.05 * min(prior_damage_index, 1.0), 3)

    damage_increment, rpm_stress_index, thermal_stress, vibration_stress = compute_hourly_damage_increment(
        rpm, temperature, vibration, deg_cfg, healthy
    )
    damage_index = prior_damage_index + damage_increment
    health_score = float(np.clip(100.0 * (1.0 - min(damage_index, 1.0)), 0.0, 100.0))

    failure_threshold = CONFIG["failure_threshold"]
    if damage_increment > 1e-9:
        remaining_hours = max(0.0, (failure_threshold - damage_index) / damage_increment)
    else:
        remaining_hours = float("inf")

    status = _status_from_health(health_score, damage_index, CONFIG)

    return {
        "unit_id": unit_id,
        "rpm": rpm,
        "operating_hours": 1,
        "temperature": round(temperature, 2),
        "vibration": round(vibration, 3),
        "pressure": round(pressure, 2),
        "loading": loading,
        "rpm_stress_index": round(rpm_stress_index, 4),
        "thermal_stress": round(thermal_stress, 4),
        "vibration_stress": round(vibration_stress, 4),
        "damage_index": round(damage_index, 5),
        "health_score": round(health_score, 2),
        "threshold": failure_threshold,
        "predicted_remaining_hours": round(remaining_hours, 1) if np.isfinite(remaining_hours) else remaining_hours,
        "status": status,
    }


def simulate_units_rpm_scenarios(df_history: pd.DataFrame, predict_fn, feature_cols: list,
                                  n_units: int | None = None) -> pd.DataFrame:
    """
    For every simulated turbine unit, run each configured RPM scenario
    (3000/4000/5000/6000) for exactly one hour, starting from that unit's own
    current wear state (its last known damage_index / operating hours from
    df_history). Reports both the physics-based remaining-hours estimate and
    the AutoGluon/RandomForest model's own predicted RUL for the same
    post-scenario state, so the two can be compared side by side.
    """
    all_unit_ids = sorted(df_history["unit_id"].unique())

    if n_units is None:
        # Use config value if it exists; otherwise use all units.
        n_units = CONFIG.get("num_scenario_units")

    if n_units is None:
        unit_ids = all_unit_ids
    else:
        unit_ids = all_unit_ids[:n_units]

    scenario_rpms = CONFIG["scenario_rpms"]

    rows = []
    for unit_id in unit_ids:
        unit_hist = df_history[df_history["unit_id"] == unit_id].sort_values("cycle").reset_index(drop=True)
        # Use a mid-life snapshot (~50% through this unit's recorded life) as
        # the "current" inspection point for the scenario, rather than the
        # very last recorded cycle (which, by construction of the historical
        # dataset, already sits at/near end-of-life for every unit).
        mid_cycle = int(round(unit_hist["cycle"].max() * 0.5))
        mid_idx = (unit_hist["cycle"] - mid_cycle).abs().idxmin()
        current_row = unit_hist.loc[mid_idx]
        prior_damage_index = float(current_row.get("damage_index", 0.0))
        prior_op_hours = float(current_row.get("operating_hours", current_row["time_hours"]))
        recent = unit_hist.iloc[max(0, mid_idx - 19):mid_idx + 1].copy()

        for rpm in scenario_rpms:
            # Unique-but-reproducible-within-this-run rng per (unit, rpm) so
            # every unit/scenario combination gets its own noise draw.
            rng = np.random.default_rng(RUN_SEED + unit_id * 97 + int(rpm))
            result = simulate_one_hour_scenario(int(unit_id), float(rpm), prior_damage_index, prior_op_hours, rng)

            # Feed the simulated post-scenario row through the trained ML
            # model too, using the unit's real recent history for context,
            # exactly as the phase-1 scenario function did.
            next_cycle = int(recent["cycle"].max()) + 1
            scenario_row = pd.DataFrame([{
                "unit_id": int(unit_id),
                "cycle": next_cycle,
                "rpm": float(rpm),
                "temperature": result["temperature"],
                "loading": result["loading"],
                "time_hours": round(prior_op_hours + 1.0, 2),
                "vibration": result["vibration"],
                "pressure": result["pressure"],
                "rul": 0,
            }])
            combined = pd.concat([recent, scenario_row], ignore_index=True)
            combined = engineer_features(combined)
            case_features = combined[feature_cols].fillna(0).iloc[[-1]]
            ml_pred_rul = float(predict_fn(case_features[feature_cols])[0])

            result["ml_predicted_rul_hours"] = round(ml_pred_rul, 2)
            rows.append(result)

    out = pd.DataFrame(rows)
    cols = ["unit_id", "rpm", "operating_hours", "temperature", "vibration", "pressure", "loading",
            "damage_index", "health_score", "threshold", "predicted_remaining_hours",
            "ml_predicted_rul_hours", "status"]
    out = out[cols]

    os.makedirs(os.path.dirname(CONFIG["scenario_table_path"]), exist_ok=True)
    out.to_csv(CONFIG["scenario_table_path"], index=False)

    print("\n=== One-Hour RPM Scenario Table (All Simulated Units) ===")
    print(out.rename(columns={
        "unit_id": "Unit", "rpm": "RPM", "operating_hours": "Hours", "temperature": "Temp",
        "vibration": "Vib", "damage_index": "Damage", "health_score": "Health",
        "threshold": "Threshold", "predicted_remaining_hours": "RUL(hrs)",
        "ml_predicted_rul_hours": "ML-RUL(hrs)", "status": "Status",
    })[["Unit", "RPM", "Hours", "Temp", "Vib", "Damage", "Health", "Threshold", "RUL(hrs)", "ML-RUL(hrs)", "Status"]]
          .to_string(index=False))
    return out


# ─────────────────────────────────────────────
# 7. NEW — Visualization
# ─────────────────────────────────────────────
def generate_visualizations(df_history: pd.DataFrame, scenario_table: pd.DataFrame, example_unit_id: int | None = None):
    """
    Produces the requested plots:
      - Health Score vs Time
      - Damage Index vs Time
      - RPM vs RUL (from the scenario table, across units)
      - Temperature vs Time
      - Vibration vs Time
      - Threshold crossing (damage index vs time with the failure threshold line)
    Saved as PNGs under CONFIG["plots_dir"].
    """
    plots_dir = CONFIG["plots_dir"]
    os.makedirs(plots_dir, exist_ok=True)

    if example_unit_id is None:
        example_unit_id = int(df_history["unit_id"].iloc[0])
    unit_df = df_history[df_history["unit_id"] == example_unit_id].sort_values("cycle")

    fig, axes = plt.subplots(2, 2, figsize=(11, 8))

    axes[0, 0].plot(unit_df["time_hours"], unit_df["health_index"], color="tab:green")
    axes[0, 0].set_title(f"Health Score vs Time (Unit {example_unit_id})")
    axes[0, 0].set_xlabel("Operating Hours")
    axes[0, 0].set_ylabel("Health Score")

    axes[0, 1].plot(unit_df["time_hours"], unit_df["damage_index"], color="tab:red")
    axes[0, 1].axhline(CONFIG["failure_threshold"], color="black", linestyle="--", label="Failure threshold")
    axes[0, 1].set_title(f"Damage Index vs Time — Threshold Crossing (Unit {example_unit_id})")
    axes[0, 1].set_xlabel("Operating Hours")
    axes[0, 1].set_ylabel("Damage Index")
    axes[0, 1].legend()

    axes[1, 0].plot(unit_df["time_hours"], unit_df["temperature"], color="tab:orange")
    axes[1, 0].set_title(f"Temperature vs Time (Unit {example_unit_id})")
    axes[1, 0].set_xlabel("Operating Hours")
    axes[1, 0].set_ylabel("Temperature (K)")

    axes[1, 1].plot(unit_df["time_hours"], unit_df["vibration"], color="tab:purple")
    axes[1, 1].set_title(f"Vibration vs Time (Unit {example_unit_id})")
    axes[1, 1].set_xlabel("Operating Hours")
    axes[1, 1].set_ylabel("Vibration")

    fig.tight_layout()
    combined_path = os.path.join(plots_dir, f"unit_{example_unit_id}_degradation_overview.png")
    fig.savefig(combined_path, dpi=150)
    plt.close(fig)
    log.info(f"Saved degradation overview plot to {combined_path}")

    # RPM vs RUL, across all simulated units/scenarios
    fig2, ax2 = plt.subplots(figsize=(7, 5))
    for uid, grp in scenario_table.groupby("unit_id"):
        grp_sorted = grp.sort_values("rpm")
        ax2.plot(grp_sorted["rpm"], grp_sorted["predicted_remaining_hours"], marker="o", label=f"Unit {uid}")
    ax2.set_title("RPM vs Predicted Remaining Hours (All Units)")
    ax2.set_xlabel("RPM")
    ax2.set_ylabel("Predicted Remaining Hours")
    ax2.legend()
    fig2.tight_layout()
    rpm_rul_path = os.path.join(plots_dir, "rpm_vs_rul.png")
    fig2.savefig(rpm_rul_path, dpi=150)
    plt.close(fig2)
    log.info(f"Saved RPM vs RUL plot to {rpm_rul_path}")

    return [combined_path, rpm_rul_path]


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
    log.info("  Turbine RUL Prediction — Multi-Sensor Degradation Simulator")
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
    log.info(f"Failure threshold (damage index): {CONFIG['failure_threshold']} | Health threshold: {CONFIG['health_threshold']}")

    # 1. Data (now includes vibration + pressure)
    df = load_paper_dataset()

    # 2. Features (now includes damage_index / health_index / etc.)
    df = engineer_features(df)
    os.makedirs("data/processed", exist_ok=True)
    df.to_csv(CONFIG["processed_path"], index=False)

    # 3. Split — by whole unit, no leakage
    X_train, X_test, y_train, y_test = split_data(df)

    # 4. Train the single final model (AutoGluon, or RandomForest fallback)
    model_name, predict_fn, metrics = train_final_model(X_train, y_train, X_test, y_test)

    # 5. Combined display — one block, one model
    display_final_model_results(model_name, metrics)

    # 6. Combined ML prediction summary for selected cycles (1, 10, 60, 120)
    feature_cols = list(X_train.columns)
    predict_for_selected_cycles(predict_fn, feature_cols, df, unit_ids=None, cycles=[1, 10, 60, 120])

    # 7. NEW — one-hour RPM scenario simulation (3000/4000/5000/6000) across
    #    multiple independent turbine units, using the physics-based damage
    #    model alongside the trained ML model for comparison.
    scenario_table = simulate_units_rpm_scenarios(df, predict_fn, feature_cols)

    # 8. NEW — visualizations
    generate_visualizations(df, scenario_table)

    log.info("Multi-sensor RPM-scenario RUL simulation complete.")


if __name__ == "__main__":
    main()