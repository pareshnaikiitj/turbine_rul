import io
import logging

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd

try:
    from backend.rul_predictor import (
        simulate_fresh_turbine_to_failure,
        get_trained_model,
        predict_rul_for_sensor_reading,
        predict_rul_for_dataframe,
        get_health_thresholds,
        _status_from_rul,
    )
except ModuleNotFoundError:
    from rul_predictor import (
        simulate_fresh_turbine_to_failure,
        get_trained_model,
        predict_rul_for_sensor_reading,
        predict_rul_for_dataframe,
        get_health_thresholds,
        _status_from_rul,
    )

app = FastAPI(title="Turbine RUL API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://turbine-rul-id2i-five.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _warm_model_cache() -> None:
    try:
        get_trained_model()
    except Exception as exc:
        logging.getLogger(__name__).warning(f"Startup model warmup failed: {exc}")


class SensorPayload(BaseModel):
    unit_id: int = 1
    cycle: int = 34
    rpm: float = 5200
    loading: float = 0.72
    vibration: float = 0.58
    pressure: float = 0.82
    time_hours: float = 18.5


class SimulationPayload(BaseModel):
    rpm: float = 6000
    stress_mpa: float | None = None
    max_hours: int = 2000


def simulate_prediction(values: SensorPayload) -> dict:
    predicted = max(0.0, predict_rul_for_sensor_reading(values.model_dump()))
    status, health_score = _status_from_rul(predicted)
    degradation_curve = simulate_fresh_turbine_to_failure(rpm=float(values.rpm), max_hours=2000)
    return {
        "predicted_rul_hours": round(float(predicted), 2),
        "health_score": health_score,
        "status": status,
        "degradation_curve": degradation_curve.head(4).to_dict(orient="records"),
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "turbine-rul-api", "version": "1.0.0", "timestamp": "2026-08-02T00:00:00Z"}


@app.post("/predict")
def predict(payload: SensorPayload) -> dict:
    try:
        return simulate_prediction(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {exc}")


@app.get("/metrics")
def metrics() -> dict:
    try:
        cache = get_trained_model()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Model training/loading failed: {exc}")

    m = cache["metrics"]
    return {
        "model": cache["model_name"],
        "test_mae_hours": round(float(m["mae"]), 2),
        "test_rmse_hours": round(float(m["rmse"]), 2),
        "r2_score": round(float(m["r2"]), 4),
    }


@app.post("/metrics/retrain")
def retrain_metrics() -> dict:
    try:
        cache = get_trained_model(force_retrain=True)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Model retraining failed: {exc}")

    m = cache["metrics"]
    return {
        "model": cache["model_name"],
        "test_mae_hours": round(float(m["mae"]), 2),
        "test_rmse_hours": round(float(m["rmse"]), 2),
        "r2_score": round(float(m["r2"]), 4),
    }


@app.get("/config/thresholds")
def config_thresholds() -> dict:
    """Health/warning/failure thresholds, straight from CONFIG — lets the
    UI render an accurate legend instead of hardcoding the numbers."""
    return get_health_thresholds()


@app.post("/simulate-fresh-turbine")
def simulate_fresh_turbine(payload: SimulationPayload) -> dict:
    try:
        curve = simulate_fresh_turbine_to_failure(
            rpm=float(payload.rpm),
            stress_mpa=float(payload.stress_mpa) if payload.stress_mpa is not None else None,
            max_hours=int(payload.max_hours),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {exc}")

    return {
        "rpm": float(payload.rpm),
        "stress_mpa": float(payload.stress_mpa) if payload.stress_mpa is not None else None,
        "max_hours": int(payload.max_hours),
        "estimated_operating_life_hours": round(float(curve["hour"].iloc[-1]), 2) if not curve.empty else 0.0,
        "degradation_curve": curve.to_dict(orient="records"),
    }


@app.post("/predict-csv")
async def predict_csv(file: UploadFile = File(...)) -> dict:
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {exc}")

    try:
        result_df = predict_rul_for_dataframe(df)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {exc}")

    cache = get_trained_model()
    return {
        "filename": file.filename,
        "model": cache["model_name"],
        "row_count": len(result_df),
        "thresholds": get_health_thresholds(),
        "predictions": result_df.to_dict(orient="records"),
    }