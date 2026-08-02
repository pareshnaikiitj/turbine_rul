# Turbine Blade RUL Prediction
### Three-Layer AutoGluon Stacked ML Approach
**Project: M25DE2039 | Paresh Naik | M.Tech Data Engineering**
*Guide: Dr. Ambuj Kumar Gautam, Dept. of Mechanical Engineering*

---

## Project Phases

| Phase | Parameter Added | Status |
|-------|----------------|--------|
| Phase 1 | `temperature` | ✅ Active |
| Phase 2 | `vibration` | ✅ Active |
| Phase 3 | `pressure` | ✅ Active |
| Phase 4 | `rpm` | ✅ Active |
| Phase 5 | `torque` | 🔜 Pending |

---

## Quick Start

```bash
# 1) Install backend dependencies in the same Python environment that will launch the API
pip install -r backend/requirements.txt

# If the shell reports `No module named uvicorn`, install the API runtime explicitly
python -m pip install uvicorn fastapi

# 2) Start the FastAPI prediction API
# If port 8000 is already occupied, stop the old process or start on another free port
python -m uvicorn backend.api:app --host 0.0.0.0 --port 8000

# 3) Install frontend dependencies
cd frontend
npm install

# 4) Start frontend UI
npm run dev -- --host 0.0.0.0
```

### Run commands from the repository root

```bash
# Backend API (from repo root)
python -m pip install uvicorn fastapi
python -m uvicorn backend.api:app --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

### Alternate backend command when already inside the backend folder

```bash
# Backend API (when your current working directory is backend/)
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

> Use `backend.api:app` only when the shell is started from the repository root. If you are already inside the `backend/` folder, use `api:app` instead.

---

## Project Structure

```
turbine_rul/
├── backend/
│   ├── rul_predictor.py   # Main backend training / prediction pipeline
│   ├── config.py          # Backend configuration and feature defaults
│   ├── requirements.txt   # Backend Python dependencies
│   ├── logs/              # Backend execution logs
│   ├── models/            # Backend model artifacts
│   ├── plots/             # Backend output plots
│   ├── data/              # Backend-local data staging
│   └── tests/             # Backend regression tests
├── frontend/
│   ├── src/               # React UI source
│   ├── package.json       # Frontend dependencies and scripts
│   └── .gitignore         # Frontend ignore rules
└── README.md              # Project overview and usage notes
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

1. Open `backend/rul_predictor.py`
2. Update `CONFIG["input_features"]` to include the new parameter
3. Re-run the pipeline — feature engineering auto-scales

```python
"input_features": [
    "temperature",   # Phase 1 ✅
    "vibration",     # Phase 2 ✅
    "pressure",      # Phase 3 ✅
    "rpm",           # Phase 4 ✅
]
```
