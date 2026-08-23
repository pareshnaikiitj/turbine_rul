#!/usr/bin/env bash
set -Eeuo pipefail

# ============================================================
# Turbine RUL Backend - EC2 complete setup + run
#
# Project:
#   /home/ubuntu/turbine_rul/backend/
#
# This script:
#   1. Creates/uses backend/venv
#   2. Uses the EC2 root disk for pip temporary files
#   3. Installs every dependency in requirements.txt
#   4. Installs CPU-only PyTorch separately (safe for normal EC2)
#   5. Installs python-multipart for FastAPI file uploads
#   6. Verifies important imports
#   7. Verifies api:app can be imported
#   8. Starts Uvicorn on 127.0.0.1:8000 for Nginx
#
# Usage:
#   chmod +x start_backend.sh
#   ./start_backend.sh
#
# Optional:
#   HOST=0.0.0.0 ./start_backend.sh
#
# For a normal CPU EC2 instance, keep the default CPU PyTorch.
# For a GPU EC2 instance, do not use the CPU PyTorch section;
# install the CUDA build appropriate for that instance instead.
# ============================================================

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$BACKEND_DIR/venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

TMP_DIR="${TMPDIR:-$HOME/pip-tmp}"
mkdir -p "$TMP_DIR"
export TMPDIR="$TMP_DIR"

cleanup() {
    rm -f "$BACKEND_DIR/requirements.runtime.tmp"
}
trap cleanup EXIT

echo
echo "============================================================"
echo " Turbine RUL FastAPI Backend"
echo "============================================================"
echo "Backend : $BACKEND_DIR"
echo "Python  : $PYTHON_BIN"
echo "Host    : $HOST"
echo "Port    : $PORT"
echo "TMPDIR  : $TMPDIR"
echo "============================================================"
echo

cd "$BACKEND_DIR"

# ------------------------------------------------------------
# 1. Check project files
# ------------------------------------------------------------
[[ -f "$BACKEND_DIR/api.py" ]] || {
    echo "ERROR: api.py not found in $BACKEND_DIR"
    exit 1
}

[[ -f "$BACKEND_DIR/requirements.txt" ]] || {
    echo "ERROR: requirements.txt not found in $BACKEND_DIR"
    exit 1
}

command -v "$PYTHON_BIN" >/dev/null 2>&1 || {
    echo "ERROR: $PYTHON_BIN is not installed."
    exit 1
}

echo "Python version:"
"$PYTHON_BIN" --version

# ------------------------------------------------------------
# 2. Disk check
# ------------------------------------------------------------
echo
echo "Disk space:"
df -h "$BACKEND_DIR" "$TMPDIR" | tail -n +1

# ------------------------------------------------------------
# 3. Create virtual environment
# ------------------------------------------------------------
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    echo
    echo "Creating virtual environment..."

    if ! "$PYTHON_BIN" -m venv "$VENV_DIR"; then
        echo
        echo "ERROR: Could not create virtual environment."
        echo "Install the matching Ubuntu venv package, for example:"
        echo "  sudo apt update"
        echo "  sudo apt install python3.14-venv -y"
        exit 1
    fi
fi

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

echo
echo "Virtual environment:"
"$VENV_PYTHON" --version
"$VENV_PYTHON" -m pip --version

# ------------------------------------------------------------
# 4. Upgrade pip tools
# ------------------------------------------------------------
echo
echo "Upgrading pip/setuptools/wheel..."
"$VENV_PYTHON" -m pip install --no-cache-dir --upgrade pip setuptools wheel

# ------------------------------------------------------------
# 5. Install all requirements EXCEPT torch
#
# torch is handled separately below so a normal CPU EC2 does
# not accidentally pull the CUDA/NVIDIA stack.
# ------------------------------------------------------------
echo
echo "Preparing runtime requirements..."

grep -vE '^[[:space:]]*torch([<=>~!].*)?([[:space:]]*#.*)?$' \
    "$BACKEND_DIR/requirements.txt" \
    > "$BACKEND_DIR/requirements.runtime.tmp"

echo
echo "Installing requirements.txt dependencies (excluding torch)..."
"$VENV_PIP" install --no-cache-dir -r "$BACKEND_DIR/requirements.runtime.tmp"

# ------------------------------------------------------------
# 6. FastAPI file uploads
#
# api.py uses UploadFile/File, which requires python-multipart.
# ------------------------------------------------------------
echo
echo "Installing FastAPI multipart support..."
"$VENV_PIP" install --no-cache-dir "python-multipart>=0.0.9"

# ------------------------------------------------------------
# 7. Install CPU-only PyTorch
#
# This is appropriate for a normal CPU EC2 instance.
# Official PyTorch provides a CPU-only package index.
# ------------------------------------------------------------
echo
echo "Installing CPU-only PyTorch..."
echo "This avoids the CUDA/NVIDIA packages that previously filled"
echo "the temporary filesystem."

"$VENV_PIP" install --no-cache-dir \
    "torch>=2.0" \
    --index-url https://download.pytorch.org/whl/cpu

# ------------------------------------------------------------
# 8. Verify important dependencies
# ------------------------------------------------------------
echo
echo "============================================================"
echo " Verifying dependencies"
echo "============================================================"

"$VENV_PYTHON" - <<'PY'
packages = [
    ("numpy", "numpy"),
    ("pandas", "pandas"),
    ("scipy", "scipy"),
    ("sklearn", "scikit-learn"),
    ("xgboost", "xgboost"),
    ("matplotlib", "matplotlib"),
    ("seaborn", "seaborn"),
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("multipart", "python-multipart"),
    ("torch", "torch"),
]

failed = []

for module, package in packages:
    try:
        m = __import__(module)
        version = getattr(m, "__version__", "installed")
        print(f"OK   {package}: {version}")
    except Exception as exc:
        print(f"FAIL {package}: {type(exc).__name__}: {exc}")
        failed.append(package)

if failed:
    print("\nDependency verification failed:")
    for package in failed:
        print(f"  - {package}")
    raise SystemExit(1)

import torch
print(f"\nPyTorch device check: CUDA available = {torch.cuda.is_available()}")
print("All required dependencies imported successfully.")
PY

# ------------------------------------------------------------
# 9. Verify rul_predictor.py
# ------------------------------------------------------------
echo
echo "Checking RUL predictor..."

"$VENV_PYTHON" - <<'PY'
try:
    import rul_predictor
    print("OK: rul_predictor imported successfully.")
except Exception as exc:
    print(f"ERROR: rul_predictor import failed: {type(exc).__name__}: {exc}")
    raise SystemExit(1)
PY

# ------------------------------------------------------------
# 10. Verify FastAPI application
# ------------------------------------------------------------
echo
echo "Checking api:app..."

"$VENV_PYTHON" - <<'PY'
try:
    import importlib
    module = importlib.import_module("api")
except Exception as exc:
    print(f"ERROR: Could not import api.py: {type(exc).__name__}: {exc}")
    raise SystemExit(1)

if not hasattr(module, "app"):
    print("ERROR: api.py does not contain an 'app' object.")
    raise SystemExit(1)

print("OK: api:app imported successfully.")
PY

# ------------------------------------------------------------
# 11. Start FastAPI
#
# Nginx should proxy:
#   api-rul.chickenkiller.com -> 127.0.0.1:8000
# ------------------------------------------------------------
echo
echo "============================================================"
echo " Starting FastAPI"
echo "============================================================"
echo "URL    : http://$HOST:$PORT"
echo "Swagger: http://$HOST:$PORT/docs"
echo
echo "Nginx should proxy to: http://127.0.0.1:8000"
echo "Press CTRL+C to stop."
echo "============================================================"
echo

exec "$VENV_PYTHON" -m uvicorn api:app \
    --host "$HOST" \
    --port "$PORT" \
    --proxy-headers