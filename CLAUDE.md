# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**DevOps Audit** — a SaaS DevOps audit tool that scans GitHub repos, Kubernetes configs, and Dockerfiles for security and best-practice issues.

Monorepo layout:

| Directory | Stack | Status |
|---|---|---|
| `backend/` | FastAPI, Python, Celery | Live |
| `frontend/` | Next.js 14, TypeScript, Tailwind | In progress |
| `infrastructure/` | Docker, Terraform | Partial (Docker only) |

## Development Setup

```bash
# Start all services (API, Celery worker, PostgreSQL, Redis)
docker compose up --build

# Run DB migrations
docker compose exec api alembic upgrade head

# API docs (Swagger UI)
http://localhost:8000/docs
```

Required environment variables: copy `backend/.env.example` to `backend/.env` and fill in GitHub OAuth credentials at minimum.

## Backend Commands

All backend commands run inside `backend/` with Poetry.

```bash
# Install dependencies
poetry install

# Run tests with coverage
poetry run pytest --cov=app

# Run a single test file or test
poetry run pytest tests/path/to/test_file.py::test_name

# Lint
poetry run ruff check .

# Type check
poetry run mypy app/
```

CI runs pytest against a live PostgreSQL 16 + Redis 7 (no mocking of the DB layer). Match this locally by running tests via `docker compose exec api poetry run pytest`.

## Frontend Commands

All frontend commands run inside `frontend/`.

```bash
# Install dependencies
npm install

# Dev server (http://localhost:3000)
npm run dev

# Production build
npm run build

# Type check
npx tsc --noEmit

# Lint
npm run lint
```

### Frontend Structure

| Path | Role |
|---|---|
| `src/app/` | Next.js 14 App Router pages |
| `src/app/auth/` | GitHub OAuth callback/login page |
| `src/app/dashboard/` | Main dashboard after login |
| `src/app/scans/` | Scan list and detail views |
| `src/components/` | Shared React components (`ScanCard`, `NewScanModal`) |
| `src/lib/api.ts` | Typed API client for the FastAPI backend |

## Infrastructure

The `infrastructure/` directory currently holds Docker assets. Terraform is planned.

```
infrastructure/
└── docker/
    └── Dockerfile.backend   # Production image for the FastAPI service
```

## Architecture

### Request Flow

```
Client → FastAPI (port 8000) → Celery worker (via Redis broker)
                                    ↓
                               Scanners → GitHub API / file system
                                    ↓
                            PostgreSQL (results) + S3 (PDF reports)
```

### Key Layers

| Layer | Path | Role |
|---|---|---|
| API routes | `backend/app/api/v1/endpoints/` | Auth, users, scan CRUD |
| Core | `backend/app/core/` | Config (Pydantic settings), DB engine, JWT/bcrypt security |
| Models | `backend/app/models/models.py` | SQLAlchemy ORM: User, Scan, Report |
| Scanners | `backend/app/scanners/` | Stateless scan logic; return structured dicts |
| Workers | `backend/app/workers/` | Celery app config + async task wrappers that call scanners |
| Services | `backend/app/services/` | GitHub OAuth helpers |

### Scan Types

`github` · `kubernetes` · `container` · `cost` (stub) · `full` (all of the above)

Scans are dispatched via Celery (`scans` queue) and write results + a 0–100 score back to the `scans` table as JSON.

### Auth Flow

GitHub OAuth2 → JWT issued (1-day access / 30-day refresh). The OAuth `state` parameter is currently stored in an in-memory dict in `auth.py` — this is a known TODO to move to Redis.

### Infrastructure

- Local: Docker Compose (FastAPI + Celery + PostgreSQL 16 + Redis 7); frontend dev server runs separately on port 3000
- Production image: `infrastructure/docker/Dockerfile.backend`
- Prod target: AWS ECS Fargate, RDS, ElastiCache, S3/CloudFront
- Terraform: planned but no `.tf` files yet

### CI/CD (`.github/workflows/ci.yml`)

- On every push/PR: `poetry run pytest` with live PostgreSQL + Redis service containers
- On merge to `main`: Docker image built and pushed to AWS ECR (tagged with commit SHA)

## What's Not Yet Implemented

- Frontend: remaining pages and API integration (scaffolding exists in `frontend/`)
- PDF report generation (WeasyPrint is installed, `tasks.py` has a stub)
- Stripe subscription billing
- Cost analyzer scanner
- Terraform IaC (planned under `infrastructure/`)
