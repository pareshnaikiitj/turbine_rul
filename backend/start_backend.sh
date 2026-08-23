#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Turbine RUL FastAPI Backend - EC2 setup/start script
# Expected project structure:
#   turbine_rul/
#     backend/
#       api.py          # must contain: app = FastAPI(...)
#       requirements.txt
#       ...
#
# Run from backend:
#   chmod +x start_backend.sh
#   ./start_backend.sh
#
# Or from anywhere:
#   bash /home/ubuntu/turbine_rul/backend/start_backend.sh
# ============================================================

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$BACKEND_DIR/venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

echo "=============================================="
echo " Turbine RUL FastAPI Backend"
echo "=============================================="
echo "Backend: $BACKEND_DIR"
echo "Host:    $HOST"
echo "Port:    $PORT"
echo

cd "$BACKEND_DIR"

# ------------------------------------------------------------
# 1. Check required files
# ------------------------------------------------------------
if [[ ! -f "$BACKEND_DIR/api.py" ]]; then
    echo "ERROR: api.py was not found in $BACKEND_DIR"
    exit 1
fi

if [[ ! -f "$BACKEND_DIR/requirements.txt" ]]; then
    echo "ERROR: requirements.txt was not found in $BACKEND_DIR"
    exit 1
fi

# ------------------------------------------------------------
# 2. Check Python
# ------------------------------------------------------------
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "ERROR: $PYTHON_BIN is not installed."
    exit 1
fi

echo "Python:"
"$PYTHON_BIN" --version

# ------------------------------------------------------------
# 3. Create virtual environment if needed
# ------------------------------------------------------------
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    echo
    echo "Creating virtual environment..."

    if ! "$PYTHON_BIN" -m venv "$VENV_DIR"; then
        echo
        echo "ERROR: Could not create the virtual environment."
        echo "On Ubuntu, install the matching venv package, for example:"
        echo "  sudo apt update"
        echo "  sudo apt install python3.14-venv -y"
        exit 1
    fi
fi

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

# ------------------------------------------------------------
# 4. Upgrade pip
# ------------------------------------------------------------
echo
echo "Upgrading pip..."
"$VENV_PYTHON" -m pip install --upgrade pip

# ------------------------------------------------------------
# 5. Install backend dependencies
# ------------------------------------------------------------
echo
echo "Installing backend dependencies..."
"$VENV_PIP" install -r "$BACKEND_DIR/requirements.txt"

# Make sure the API runtime exists even if requirements.txt
# does not contain it.
echo
echo "Checking FastAPI/Uvicorn..."
"$VENV_PIP" install fastapi uvicorn

# ------------------------------------------------------------
# 6. Optional environment file
# ------------------------------------------------------------
if [[ -f "$BACKEND_DIR/.env" ]]; then
    echo ".env found."
else
    echo "No .env file found. Continuing..."
fi

# ------------------------------------------------------------
# 7. Check that the FastAPI application can be imported
# ------------------------------------------------------------
echo
echo "Checking api:app..."

"$VENV_PYTHON" - <<'PY'
import importlib

try:
    module = importlib.import_module("api")
except Exception as e:
    print("\nERROR: Could not import api.py")
    print(f"{type(e).__name__}: {e}")
    raise SystemExit(1)

if not hasattr(module, "app"):
    print("\nERROR: api.py does not contain an 'app' object.")
    print("Expected something similar to:")
    print("    app = FastAPI()")
    raise SystemExit(1)

print("OK: api:app imported successfully.")
PY

# ------------------------------------------------------------
# 8. Start FastAPI
#
# 127.0.0.1 is intentional when using Nginx:
#
# Internet -> Nginx :80/:443 -> FastAPI 127.0.0.1:8000
#
# To expose port 8000 directly, use:
#   HOST=0.0.0.0 ./start_backend.sh
# ------------------------------------------------------------
echo
echo "=============================================="
echo " Starting FastAPI"
echo "=============================================="
echo "URL: http://$HOST:$PORT"
echo "Swagger (if enabled): http://$HOST:$PORT/docs"
echo
echo "Press CTRL+C to stop."
echo

exec "$VENV_PYTHON" -m uvicorn api:app \
    --host "$HOST" \
    --port "$PORT" \
    --proxy-headers