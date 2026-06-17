# Turbine Blade RUL Prediction
### Three-Layer AutoGluon Stacked ML Approach
**Project: M25DE2039 | Paresh Naik | M.Tech Data Engineering**
*Guide: Dr. Ambuj Kumar Gautam, Dept. of Mechanical Engineering*

---

## Project Phases

| Phase | Parameter Added | Status |
|-------|----------------|--------|
| Phase 1 | `temperature` | ✅ Active |
| Phase 2 | `vibration` | 🔜 Pending |
| Phase 3 | `pressure` | 🔜 Pending |
| Phase 4 | `rpm` | 🔜 Pending |
| Phase 5 | `torque` | 🔜 Pending |

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run Phase 1 (temperature only)
python src/rul_predictor.py
```

---

## Project Structure

```
turbine_rul/
├── data/
│   ├── raw/               # Sensor CSV files (real or synthetic)
│   └── processed/         # Engineered feature sets
├── src/
│   └── rul_predictor.py   # Main training pipeline
├── models/
│   └── autogluon_rul/     # Saved AutoGluon predictor
├── notebooks/             # EDA and analysis notebooks
├── logs/                  # Training logs
└── requirements.txt
```

---

## Three-Layer Ensemble Architecture

```
Input (Temperature + Rolling Features)
         │
    ┌────▼─────┐
    │  Layer 1 │  Random Forest (base learner)
    └────┬─────┘
         │ OOF predictions
    ┌────▼─────┐
    │  Layer 2 │  XGBoost (residual corrector)
    └────┬─────┘
         │ OOF predictions
    ┌────▼─────┐
    │  Layer 3 │  PyTorch Neural Net (deep learner)
    └────┬─────┘
         │
    ┌────▼─────────────────┐
    │  Weighted Ensemble   │  → RUL Prediction (hours)
    └──────────────────────┘
```

---

## Adding a New Parameter

1. Open `src/rul_predictor.py`
2. Uncomment the next parameter in `CONFIG["input_features"]`
3. Re-run the pipeline — feature engineering auto-scales

```python
"input_features": [
    "temperature",   # Phase 1 ✅
    "vibration",     # Phase 2 — uncomment when ready
]
```
