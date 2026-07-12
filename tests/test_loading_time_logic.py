import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rul_predictor import build_paper_dataset, summarize_loading_comparison


def test_loading_and_time_scale_with_rpm():
    df = build_paper_dataset()

    low_rpm_row = df[(df["unit_id"] == 5) & (df["cycle"] == 1)].iloc[0]
    high_rpm_row = df[(df["unit_id"] == 4) & (df["cycle"] == 1)].iloc[0]

    assert "loading" in df.columns
    assert "time_hours" in df.columns
    assert high_rpm_row["loading"] > low_rpm_row["loading"]
    assert high_rpm_row["time_hours"] >= low_rpm_row["time_hours"]


def test_loading_scenario_comparison_reports_min_max_and_total_hours():
    df = build_paper_dataset()

    def dummy_predict(X):
        loading = float(X["loading"].iloc[0])
        return np.array([120.0 if loading <= 0.7 else 80.0])

    comparison = summarize_loading_comparison(df, predict_fn=dummy_predict, feature_cols=["loading", "time_hours"], sample_rows=df.head(1))

    assert comparison["min_loading"]["loading"] <= comparison["max_loading"]["loading"]
    assert comparison["min_loading"]["predicted_rul_hours"] >= comparison["max_loading"]["predicted_rul_hours"]
    assert comparison["min_loading"]["total_hours"] >= comparison["max_loading"]["total_hours"]
