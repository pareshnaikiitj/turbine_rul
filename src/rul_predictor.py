"""
Turbine Blade RUL Prediction - 
======================================================
Project  : M25DE2039 - Prediction of Remaining Useful Life of Turbine Blades
Author   : Paresh Naik | Roll No: M25DE2039
Guide    : Dr. Ambuj Kumar Gautam
Branch   : Data Engineering (M.Tech)

Stage    : Phase 1 — Parameters (RPM, Temperature, Loading)
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
# 1. Data loading — REAL DATA (persistent store) with synthetic fallback
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
    SYNTHETIC FALLBACK ONLY — used when no real data store exists yet and
    no uploaded_csv_path was supplied. Builds a journal-paper-based turbine
    dataset from the reported operating points and healthy blade ranges.
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
            loading, time_hours = calculate_loading_and_time(rpm, cycle, life, healthy)
            rul = max(0, life - cycle)
            rows.append({
                "unit_id": unit_id,
                "cycle": cycle,
                "rpm": round(rpm, 2),
                "temperature": round(temperature, 2),
                "loading": loading,
                "time_hours": time_hours,
                "rul": int(rul),
            })

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(CONFIG["journal_data_path"]), exist_ok=True)
    df.to_csv(CONFIG["journal_data_path"], index=False)
    log.info(f"Built SYNTHETIC fallback dataset at {CONFIG['journal_data_path']} ({len(df)} rows)")
    return df


def load_and_store_real_data(uploaded_csv_path: str) -> pd.DataFrame:
    """
    Load the user's REAL raw CSV (unit_id, cycle, rpm, temperature, loading,
    time_hours, rul) and merge it into a persistent store on disk, instead
    of overwriting or regenerating synthetic data. Existing stored rows for
    a given (unit_id, cycle) are kept as OLD DATA; any new rows from
    `uploaded_csv_path` are treated as CURRENT DATA and appended. Duplicate
    (unit_id, cycle) pairs are resolved in favor of the newly uploaded row.
    """
    store_path = CONFIG["real_data_store_path"]
    os.makedirs(os.path.dirname(store_path), exist_ok=True)

    new_data = pd.read_csv(uploaded_csv_path)
    required_cols = {"unit_id", "cycle", "rpm", "temperature", "loading", "time_hours", "rul"}
    missing = required_cols - set(new_data.columns)
    if missing:
        raise ValueError(f"Uploaded real data is missing required columns: {missing}")

    if os.path.exists(store_path):
        old_data = pd.read_csv(store_path)
        combined = pd.concat([old_data, new_data], ignore_index=True)
        combined = combined.drop_duplicates(subset=["unit_id", "cycle"], keep="last")
    else:
        combined = new_data.copy()

    combined = combined.sort_values(["unit_id", "cycle"]).reset_index(drop=True)
    combined.to_csv(store_path, index=False)
    log.info(f"Real data store updated: {len(new_data)} new rows merged, {len(combined)} total rows at {store_path}")
    return combined


def load_real_data_store() -> pd.DataFrame:
    """Load the persistent real-data store as-is (no new upload this run)."""
    store_path = CONFIG["real_data_store_path"]
    if not os.path.exists(store_path):
        raise FileNotFoundError(
            f"No real data store found at {store_path}. "
            f"Call load_paper_dataset(uploaded_csv_path=...) first, or set "
            f"CONFIG['use_real_data'] = False to use synthetic data."
        )
    return pd.read_csv(store_path)


def load_paper_dataset(uploaded_csv_path: str | None = None) -> pd.DataFrame:
    """
    Data source selector:
      - If `uploaded_csv_path` is given, ingest it as CURRENT DATA and merge
        into the persistent real-data store (OLD DATA + CURRENT DATA).
      - Else, if CONFIG["use_real_data"] is True and a store already exists
        on disk, load that accumulated real data (no synthetic generation).
      - Else, fall back to the synthetic build_paper_dataset() generator
        (only used when no real data is available at all).
    """
    if uploaded_csv_path is not None:
        return load_and_store_real_data(uploaded_csv_path)

    if CONFIG.get("use_real_data", False) and os.path.exists(CONFIG["real_data_store_path"]):
        log.info("Loading accumulated real data store (no synthetic generation).")
        return load_real_data_store()

    log.info("No real data available — falling back to synthetic build_paper_dataset().")
    return build_paper_dataset()

# ─────────────────────────────────────────────
# SLMTA15 Material Fatigue Model (S-N curve + Palmgren-Miner)
#    — This is the CURRENT / final RUL prediction logic used for RPM
#      scenario forecasting, replacing the earlier Basquin-formula-based
#      physics simulator.
# ─────────────────────────────────────────────
def _stress_from_loading(loading: float) -> float:
    """Map a loading ratio (healthy_ranges['loading']) onto a stress value (MPa)."""
    healthy = CONFIG["healthy_ranges"]
    stress_cfg = CONFIG["stress_range_mpa"]
    l_min, l_max = healthy["loading"]["min"], healthy["loading"]["max"]
    ratio = float(np.clip((loading - l_min) / max(1e-9, (l_max - l_min)), 0.0, 1.0))
    return stress_cfg["min"] + ratio * (stress_cfg["max"] - stress_cfg["min"])


def _fatigue_life_cycles_slmta15(stress_mpa: float) -> float:
    """
    Interpolate fatigue life (cycles to failure) for SLMTA15 at a given
    stress, using stress vs log10(N) linear interpolation between the
    table points in CONFIG["material_sn_curve"]. Stress is clipped to the
    table's own bounds (500-900 MPa) to avoid extrapolation.
    """
    points = sorted(CONFIG["material_sn_curve"]["stress_life_points"], key=lambda p: p[0])
    stresses = [p[0] for p in points]
    log_lives = [np.log10(p[1]) for p in points]
    stress_mpa = float(np.clip(stress_mpa, stresses[0], stresses[-1]))
    log_n = float(np.interp(stress_mpa, stresses, log_lives))
    return float(10 ** log_n)


def compute_used_damage_slmta15(unit_df: pd.DataFrame, used_hours: float) -> float:
    """
    PREVIOUS DATA: walk through this unit's real recorded history up to
    `used_hours`, and accumulate Palmgren-Miner damage (sum of n_i/N_fi)
    using the SLMTA15 S-N curve at each row's own rpm/loading-derived
    stress. Returns the cumulative damage fraction (0 = brand new, 1 = at
    failure) already consumed by the time the unit reached `used_hours` of
    operation.
    """
    hist = unit_df[unit_df["time_hours"] <= used_hours].sort_values("time_hours").copy()
    if hist.empty:
        return 0.0

    hist["delta_hours"] = hist["time_hours"].diff().fillna(hist["time_hours"].iloc[0])

    damage = 0.0
    for _, row in hist.iterrows():
        stress = _stress_from_loading(float(row["loading"]))
        n_f = _fatigue_life_cycles_slmta15(stress)
        cycles_per_hour = float(row["rpm"]) * 60.0
        damage_rate_per_hour = cycles_per_hour / n_f
        damage += damage_rate_per_hour * float(row["delta_hours"])

    return float(damage)


def predict_remaining_hours_slmta15(df_history: pd.DataFrame,
                                     unit_ids: list | None = None,
                                     rpms: list | None = None,
                                     used_hours: float | None = None) -> pd.DataFrame:
    """
    FINAL PREDICTION LOGIC: for every unit, using its REAL historical
    operation (up to `used_hours`, or up to its own latest recorded row if
    used_hours is None) to compute damage already consumed
    (Palmgren-Miner + SLMTA15 S-N curve), predict the REMAINING operating
    hours if it now switches to each candidate RPM.

        remaining_hours = (1 - damage_used) * (N_f(stress_at_rpm) / (rpm * 60))

    Loading for the new scenario is anchored to this unit's OWN actual life
    span/last recorded cycle (via calculate_loading_and_time), not a
    generic assumption.
    """
    healthy = CONFIG["healthy_ranges"]
    if unit_ids is None:
        unit_ids = sorted(df_history["unit_id"].unique())
    if rpms is None:
        rpms = CONFIG.get("scenario_rpms", [3000, 4000, 5000, 6000])

    rows = []
    for unit_id in unit_ids:
        unit_df = df_history[df_history["unit_id"] == unit_id].sort_values("cycle").reset_index(drop=True)
        if unit_df.empty:
            continue

        last_row = unit_df.iloc[-1]
        last_cycle = int(last_row["cycle"])
        last_time_hours = float(last_row["time_hours"])

        # Default: treat ALL of this unit's real recorded history as "used".
        unit_used_hours = last_time_hours if used_hours is None else used_hours

        damage_used = compute_used_damage_slmta15(unit_df, unit_used_hours)
        damage_used = min(damage_used, 0.999999)

        unit_life = last_cycle
        next_cycle = last_cycle + 1

        for rpm in rpms:
            loading, _ = calculate_loading_and_time(float(rpm), next_cycle, unit_life, healthy)

            stress_mpa = _stress_from_loading(loading)
            n_f_cycles = _fatigue_life_cycles_slmta15(stress_mpa)
            cycles_per_hour = rpm * 60.0
            total_life_hours = n_f_cycles / cycles_per_hour

            remaining_fraction = max(0.0, 1.0 - damage_used)
            remaining_hours = remaining_fraction * total_life_hours

            rows.append({
                "unit_id": int(unit_id),
                "used_hours": round(unit_used_hours, 2),
                "damage_used": round(damage_used, 5),
                "rpm": float(rpm),
                "loading": loading,
                "stress_mpa": round(stress_mpa, 1),
                "fatigue_life_cycles": round(n_f_cycles, 0),
                "cycles_per_hour": int(cycles_per_hour),
                "total_life_hours": round(total_life_hours, 2),
                "predicted_remaining_hours": round(remaining_hours, 2),
            })

    out = pd.DataFrame(rows)

    output_dir = "data/output"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "rul_slmta15_material_model.csv")
    out.to_csv(output_path, index=False)
    log.info(f"Saved SLMTA15 material-model remaining-hours table to {output_path}")

    print("\n=== SLMTA15 Material Fatigue Model - Remaining Hours (per-unit real used_hours) ===")
    print("Material: SLMTA15 | Formula: cycles/hour = rpm x 60 | life_hours = N_f(stress) / cycles_per_hour")
    print("Loading is anchored to each unit's own real recorded trajectory, not a generic rpm-ratio guess.")
    print(out.rename(columns={
        "unit_id": "Unit", "used_hours": "Used(hrs)", "damage_used": "Damage Used",
        "rpm": "RPM", "loading": "Load", "stress_mpa": "Stress(MPa)", "fatigue_life_cycles": "N_f(cycles)",
        "cycles_per_hour": "Cycles/hr", "total_life_hours": "Total Life(hrs)",
        "predicted_remaining_hours": "Remaining(hrs)",
    }).to_string(index=False))

    return out

# ─────────────────────────────────────────────
#   Fresh Turbine Degradation Simulator (0 -> Failure)
#   Uses the SLMTA15 S-N curve, starting from a brand-new blade
#   (damage = 0) and stepping forward ONE HOUR at a time until failure.
# ─────────────────────────────────────────────
def simulate_fresh_turbine_to_failure(rpm: float, stress_mpa: float | None = None, max_hours: int = 2000) -> pd.DataFrame:
    """
    ... (docstring unchanged) ...
    """
    healthy = CONFIG["healthy_ranges"]
    failure_threshold = 1.0

    rpm_ratio = _rpm_ratio(rpm, healthy)

    fixed_n_f_cycles = None
    fixed_life_hours = None
    if stress_mpa is not None:
        fixed_n_f_cycles = _fatigue_life_cycles_slmta15(float(stress_mpa))
        fixed_life_hours = fixed_n_f_cycles / (rpm * 60.0)

    cumulative_damage = 0.0
    rows = []
    elapsed_hours = 0.0   # fractional-aware total hours elapsed
    step = 0

    while cumulative_damage < failure_threshold and step < max_hours:
        step += 1

        if stress_mpa is not None:
            stress = float(stress_mpa)
            n_f_cycles = fixed_n_f_cycles
        else:
            loading = round(0.45 + 0.45 * rpm_ratio + 0.05 * min(cumulative_damage, 1.0), 3)
            stress = _stress_from_loading(loading)
            n_f_cycles = _fatigue_life_cycles_slmta15(stress)

        cycles_per_hour = rpm * 60.0
        damage_increment_full_hour = cycles_per_hour / n_f_cycles
        remaining_damage = failure_threshold - cumulative_damage

        if damage_increment_full_hour >= remaining_damage:
            # Failure occurs partway through this simulated hour —
            # scale the step down to exactly how long it actually takes.
            fraction_of_hour = remaining_damage / damage_increment_full_hour
            damage_increment = remaining_damage
            cumulative_damage = failure_threshold
            hours_this_step = fraction_of_hour
            cycles_this_step = cycles_per_hour * fraction_of_hour
            status = "Failed"
        else:
            damage_increment = damage_increment_full_hour
            cumulative_damage += damage_increment
            hours_this_step = 1.0
            cycles_this_step = cycles_per_hour

            health_score = 100.0 * (1.0 - cumulative_damage)
            if health_score <= 25:
                status = "Critical"
            elif health_score <= 60:
                status = "Warning"
            else:
                status = "Healthy"

        elapsed_hours += hours_this_step
        health_score = float(np.clip(100.0 * (1.0 - cumulative_damage), 0.0, 100.0))

        rows.append({
            "hour": round(elapsed_hours, 4),
            "cycle": round(elapsed_hours, 4),
            "rpm": rpm,
            "stress_mpa": round(stress, 1),
            "cycles_per_hour": int(cycles_per_hour),
            "cycles_this_step": round(cycles_this_step, 0),
            "damage_increment": round(damage_increment, 6),
            "cumulative_damage": round(cumulative_damage, 5),
            "health_score": round(health_score, 2),
            "status": status,
        })

    out = pd.DataFrame(rows)

    output_dir = "data/output"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"fresh_turbine_degradation_rpm{int(rpm)}.csv")
    out.to_csv(output_path, index=False)
    log.info(f"Saved fresh-turbine degradation curve (rpm={rpm}) to {output_path}")

    total_hours_to_failure = out["hour"].iloc[-1] if not out.empty else 0
    reached_failure = not out.empty and out["cumulative_damage"].iloc[-1] >= failure_threshold

    print(f"\n=== Fresh Turbine Degradation Simulation of SLMTA15 material(0 -> Failure) ===")
    stress_desc = f"fixed {stress_mpa} MPa" if stress_mpa is not None else "derived from loading"
    fatigue_life_desc = f" | Total Fatigue life: {fixed_n_f_cycles:,.0f} cycles" if fixed_n_f_cycles is not None else ""
    life_hours_desc = f" | Estimated operating life : {fixed_life_hours:.2f} hours" if fixed_life_hours is not None else ""
    print(f"RPM: {rpm} | Stress mode: {stress_desc}{fatigue_life_desc}{life_hours_desc}")
    print(out.to_string(index=False))
    if reached_failure:
        print(f"\n>> Estimated operating life until failure: {total_hours_to_failure:.2f} hours "
              f"(~{total_hours_to_failure:.2f} simulated hours to reach damage index = 1.0)")
    else:
        print(f"\n>> Did not reach failure within max_hours={max_hours} (damage reached "
              f"{out['cumulative_damage'].iloc[-1] if not out.empty else 0:.4f})")

    return out
# ─────────────────────────────────────────────
# 2. Feature Engineering
# ─────────────────────────────────────────────
def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create rolling statistical features from the active input parameter(s):
    rolling mean/std, lag, diff, cycle progress, and a cumulative
    degradation index (cdi). Sorted by unit → cycle to preserve time-series
    order.
    """
    df = df.sort_values(["unit_id", "cycle"]).reset_index(drop=True)
    healthy = CONFIG["healthy_ranges"]

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

    df["temp_rise"] = df.groupby("unit_id")["temperature"].diff().fillna(0)
    df["loading_rise"] = df.groupby("unit_id")["loading"].diff().fillna(0)
    df["rpm_rise"] = df.groupby("unit_id")["rpm"].diff().fillna(0)
    df["operating_hours"] = df["time_hours"]
    df["running_hours"] = df.groupby("unit_id").cumcount() + 1
    df["cycle_progress"] = df.groupby("unit_id")["cycle"].rank(method="first") / df.groupby("unit_id").size().reindex(df["unit_id"]).to_numpy()
    df["cycle_progress"] = df["cycle_progress"].fillna(0)

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
    Split by whole turbine unit_id when there are enough units to do so
    (keeps every cycle of a given unit entirely in train or test, avoiding
    leakage). If there are too few units (e.g. only 1, as with a small
    test/real-data upload) to hold out a whole unit without emptying the
    training set, falls back to a per-unit TIME-BASED split instead: the
    earliest cycles of each unit go to train, the latest go to test.
    """
    drop_cols = ["unit_id", "cycle", CONFIG["target"]]
    feature_cols = [c for c in df.columns if c not in drop_cols]

    unit_ids = df["unit_id"].unique()
    rng = np.random.default_rng(CONFIG["random_state"])

    # Need at least 2 units to hold one out entirely without leaving
    # train empty. Otherwise, split by cycle within each unit.
    min_units_for_unit_split = 2

    if len(unit_ids) >= min_units_for_unit_split:
        shuffled = unit_ids.copy()
        rng.shuffle(shuffled)

        n_test_units = max(1, int(round(len(shuffled) * CONFIG["test_size"])))
        n_test_units = min(n_test_units, len(shuffled) - 1)  # always leave >=1 unit for train
        test_units = set(shuffled[:n_test_units])
        train_units = set(shuffled[n_test_units:])

        train_df = df[df["unit_id"].isin(train_units)].reset_index(drop=True)
        test_df = df[df["unit_id"].isin(test_units)].reset_index(drop=True)

        log.info(f"Split mode: by whole unit. Train units: {sorted(train_units)}  Test units: {sorted(test_units)}")
    else:
        # Fallback: time-based split within each unit's own cycles.
        train_parts, test_parts = [], []
        for unit_id in unit_ids:
            unit_df = df[df["unit_id"] == unit_id].sort_values("cycle").reset_index(drop=True)
            n = len(unit_df)
            if n < 2:
                # Not enough rows to split at all — put the single row in train.
                train_parts.append(unit_df)
                continue
            n_test = max(1, int(round(n * CONFIG["test_size"])))
            n_test = min(n_test, n - 1)  # always leave >=1 row for train
            train_parts.append(unit_df.iloc[:-n_test])
            test_parts.append(unit_df.iloc[-n_test:])

        train_df = pd.concat(train_parts, ignore_index=True) if train_parts else df.iloc[0:0]
        test_df = pd.concat(test_parts, ignore_index=True) if test_parts else df.iloc[0:0]

        log.info(f"Split mode: too few units ({len(unit_ids)}) for whole-unit split — using per-unit time-based split instead.")

    X_train, y_train = train_df[feature_cols], train_df[CONFIG["target"]]
    X_test, y_test = test_df[feature_cols], test_df[CONFIG["target"]]

    log.info(f"Train shape: {X_train.shape} | Test shape: {X_test.shape}")
    return X_train, X_test, y_train, y_test


# ─────────────────────────────────────────────
# 4. Final Model — AutoGluon Three-Layer Stacked Ensemble
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
                    num_stack_levels=2,
                    num_bag_folds=5,
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
# 5. Display + Combined ML Prediction Summary
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
    Combined table across ALL turbine units: actual rpm/temperature/loading
    + actual vs predicted RUL (from the trained ML model) for specific
    cycles (e.g. 1, 10, 60, 120).
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
# 7. Visualization
# ─────────────────────────────────────────────
def generate_visualizations(df_history: pd.DataFrame, slmta15_table: pd.DataFrame,
                             example_unit_id: int | None = None):
    """
    Temperature vs Time, Loading vs Time (from real historical data), and
    RPM vs Predicted Remaining Hours (from the SLMTA15 material model
    output), across all units.
    """
    plots_dir = CONFIG["plots_dir"]
    os.makedirs(plots_dir, exist_ok=True)

    if example_unit_id is None:
        example_unit_id = int(df_history["unit_id"].iloc[0])
    unit_df = df_history[df_history["unit_id"] == example_unit_id].sort_values("cycle")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    axes[0].plot(unit_df["time_hours"], unit_df["temperature"], color="tab:orange")
    axes[0].set_title(f"Temperature vs Time (Unit {example_unit_id})")
    axes[0].set_xlabel("Operating Hours")
    axes[0].set_ylabel("Temperature (K)")

    axes[1].plot(unit_df["time_hours"], unit_df["loading"], color="tab:blue")
    axes[1].set_title(f"Loading vs Time (Unit {example_unit_id})")
    axes[1].set_xlabel("Operating Hours")
    axes[1].set_ylabel("Loading")

    fig.tight_layout()
    combined_path = os.path.join(plots_dir, f"unit_{example_unit_id}_history_overview.png")
    fig.savefig(combined_path, dpi=150)
    plt.close(fig)
    log.info(f"Saved history overview plot to {combined_path}")

    # RPM vs Predicted Remaining Hours (SLMTA15 model), across all units
    fig2, ax2 = plt.subplots(figsize=(7, 5))
    for uid, grp in slmta15_table.groupby("unit_id"):
        grp_sorted = grp.sort_values("rpm")
        ax2.plot(grp_sorted["rpm"], grp_sorted["predicted_remaining_hours"], marker="o", label=f"Unit {uid}")
    ax2.set_title("RPM vs Predicted Remaining Hours (SLMTA15 Model, All Units)")
    ax2.set_xlabel("RPM")
    ax2.set_ylabel("Predicted Remaining Hours")
    ax2.legend()
    fig2.tight_layout()
    rpm_rul_path = os.path.join(plots_dir, "rpm_vs_remaining_hours_slmta15.png")
    fig2.savefig(rpm_rul_path, dpi=150)
    plt.close(fig2)
    log.info(f"Saved RPM vs Remaining Hours plot to {rpm_rul_path}")

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
def main(uploaded_csv_path: str | None = None):
    """
    uploaded_csv_path: path to a NEW real-data CSV to ingest this run
    (unit_id, cycle, rpm, temperature, loading, time_hours, rul). This is
    merged into the persistent real-data store as CURRENT DATA on top of
    OLD DATA from previous runs. If omitted, the accumulated store on disk
    is reused as-is (or, if no store exists yet, falls back to synthetic
    data so the pipeline never crashes on a first-time setup).
    """
    log.info("=" * 55)
    log.info("  Turbine RUL Prediction — Real-Data + SLMTA15 Material Model")
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

    # Example 1: Industrial Gas Turbine (3000 rpm, fixed stress = 700 MPa)
    simulate_fresh_turbine_to_failure(rpm=4000, stress_mpa=600)
    # Expect life_hours ≈ N_f(700MPa)/(3000*60) ≈ 4.0e6/180000 ≈ 22.22 hrs
    # (config's 700 MPa entry is now 4.0e6 cycles — the upper bound of its
    #  8e5–4e6 scatter range — matching this worked example exactly)

    # Example 2: Aircraft High-Pressure Turbine (15000 rpm, 700 MPa)
    # simulate_fresh_turbine_to_failure(rpm=15000, stress_mpa=700)

    # # Example 3: Aircraft Low-Pressure Turbine (6000 rpm, 700 MPa)
    # simulate_fresh_turbine_to_failure(rpm=6000, stress_mpa=700)

    # # Realistic mode: stress evolves naturally from loading as the turbine ages
    # simulate_fresh_turbine_to_failure(rpm=6000, stress_mpa=None)

    # 1. Data — REAL data (old + current, accumulated in the persistent
    #    store), with synthetic fallback only if nothing real exists yet.
    df = load_paper_dataset(uploaded_csv_path=uploaded_csv_path)
    log.info(f"Loaded dataset: {len(df)} rows across {df['unit_id'].nunique()} unit(s)")

    # 2. Features
    df = engineer_features(df)
    os.makedirs("data/processed", exist_ok=True)
    df.to_csv(CONFIG["processed_path"], index=False)

    # 3. Split — by whole unit, no leakage
    X_train, X_test, y_train, y_test = split_data(df)

    # 4. Train the single final ML model (AutoGluon, or RandomForest fallback)
    model_name, predict_fn, metrics = train_final_model(X_train, y_train, X_test, y_test)

    # 5. Combined display — one block, one model
    # display_final_model_results(model_name, metrics)
    

    # 6. ML prediction summary for selected cycles (1, 10, 60, 120)
    feature_cols = list(X_train.columns)
    predict_for_selected_cycles(predict_fn, feature_cols, df, unit_ids=None, cycles=[1, 10, 60, 120])

    # 7. FINAL / CURRENT prediction logic — SLMTA15 material fatigue model.
    #    used_hours=None means each unit uses ITS OWN real accumulated
    #    time_hours (all of its real history counts as "used").
    # slmta15_table = predict_remaining_hours_slmta15(df, unit_ids=None, rpms=None, used_hours=None)

    # 8. Visualizations
    # generate_visualizations(df, slmta15_table)

    log.info("Real-data SLMTA15 RUL prediction complete.")


if __name__ == "__main__":
    # First run: point at your real CSV to ingest it into the persistent  
    # store. Later runs can call main() with no argument to reuse/extend
    # the accumulated store, or pass a new CSV of freshly recorded rows.
    main(uploaded_csv_path="data/raw/turbine_unit1_upload.csv")