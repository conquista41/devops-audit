#!/usr/bin/env bash
# Run this once after cloning: bash demo_start.sh
# Requires Docker Desktop (or Docker Engine + Compose v2)
set -euo pipefail

echo "=== DevOps Audit — demo setup ==="
echo ""

# Copy demo .env if none exists
if [ ! -f backend/.env ]; then
    cp backend/.env.demo backend/.env
    echo "Created backend/.env from .env.demo"
fi

# Build and start all services detached
echo "Building and starting services (first run may take a few minutes)..."
docker compose up --build -d

# Wait for the API container to be ready, then run migrations
echo "Waiting for API container to be ready..."
RETRIES=0
until docker compose exec -T api python -c "import app.core.database" 2>/dev/null; do
    RETRIES=$((RETRIES + 1))
    if [ "$RETRIES" -ge 15 ]; then
        echo ""
        echo "ERROR: API container did not become ready. Check logs:"
        echo "  docker compose logs api"
        exit 1
    fi
    printf "."
    sleep 3
done
echo ""

echo "Running database migrations..."
docker compose exec -T api alembic upgrade head

echo ""
echo "Ready."
echo ""
echo "  Frontend   http://localhost:3000"
echo "  API docs   http://localhost:8000/docs"
echo ""
echo "Demo login (no GitHub account needed):"
echo "  curl -s -X POST http://localhost:8000/api/v1/auth/demo | python3 -m json.tool"
echo ""
echo "Logs:  docker compose logs -f"
echo "Stop:  docker compose down"
