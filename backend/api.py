from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from backend.rul_predictor import simulate_fresh_turbine_to_failure
except ModuleNotFoundError:
    from rul_predictor import simulate_fresh_turbine_to_failure

app = FastAPI(title="Turbine RUL API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://127.0.0.1:5173", 
        "https://turbine-rul-id2i-nsh7a0wtb-pareshnaikiitjs-projects.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SensorPayload(BaseModel):
    unit_id: int = 1
    cycle: int = 34
    rpm: float = 5200
    temperature: float = 720
    loading: float = 0.72
    vibration: float = 0.58
    pressure: float = 0.82
    time_hours: float = 18.5


class SimulationPayload(BaseModel):
    rpm: float = 6000
    stress_mpa: float | None = None
    max_hours: int = 2000


def simulate_prediction(values: SensorPayload) -> dict:
    rpm = float(values.rpm)
    temperature = float(values.temperature)
    loading = float(values.loading)
    vibration = float(values.vibration)
    pressure = float(values.pressure)
    time_hours = float(values.time_hours)

    predicted = max(
        0,
        165
        - (rpm / 95)
        - (temperature * 0.05)
        - (loading * 65)
        - (vibration * 40)
        - (pressure * 30)
        + (time_hours * 1.4),
    )

    degradation_curve = simulate_fresh_turbine_to_failure(rpm=rpm, max_hours=2000)

    return {
        "predicted_rul_hours": round(float(predicted), 2),
        "health_score": round(max(0, min(100, 100 - predicted / 1.8)), 1),
        "status": "Critical" if predicted < 40 else "Watch" if predicted < 90 else "Healthy",
        "degradation_curve": degradation_curve.head(4).to_dict(orient="records"),
    }


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "turbine-rul-api",
        "version": "1.0.0",
        "timestamp": "2026-08-02T00:00:00Z",
    }


@app.post("/predict")
def predict(payload: SensorPayload) -> dict:
    return simulate_prediction(payload)


@app.post("/simulate-fresh-turbine")
def simulate_fresh_turbine(payload: SimulationPayload) -> dict:
    curve = simulate_fresh_turbine_to_failure(
        rpm=float(payload.rpm),
        stress_mpa=float(payload.stress_mpa) if payload.stress_mpa is not None else None,
        max_hours=int(payload.max_hours),
    )

    return {
        "rpm": float(payload.rpm),
        "stress_mpa": float(payload.stress_mpa) if payload.stress_mpa is not None else None,
        "max_hours": int(payload.max_hours),
        "estimated_operating_life_hours": round(float(curve["hour"].iloc[-1]), 2) if not curve.empty else 0.0,
        "degradation_curve": curve.to_dict(orient="records"),
    }
