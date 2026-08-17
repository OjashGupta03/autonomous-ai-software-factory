#!/usr/bin/env bash
# Local dev setup without Docker (see docs/20-local-development.md for
# the full walkthrough and the Docker-based alternative).
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Backend: creating virtualenv and installing dependencies"
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt

if [ ! -f ../.env ]; then
    echo "==> Copying .env.example -> .env (edit it before running anything for real)"
    cp ../.env.example ../.env
fi

echo "==> Running Alembic migrations (requires Postgres reachable at DATABASE_URL)"
alembic upgrade head || echo "Migration failed - is Postgres running? See docs/20-local-development.md."

echo "==> Backend ready. Start it with:"
echo "    cd backend && source .venv/bin/activate && uvicorn app.main:app --reload"
echo "==> Start a worker with:"
echo "    cd backend && source .venv/bin/activate && arq app.workers.tasks.WorkerSettings"

cd ../frontend
echo "==> Frontend: installing dependencies"
npm install

echo ""
echo "==> Setup complete. Frontend: cd frontend && npm run dev"
