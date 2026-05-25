# HealthCheck.dev

A SaaS DevOps audit tool that scans GitHub repositories, Kubernetes configs, and Dockerfiles for security issues and misconfigurations. Runs as a background job via Celery and returns a 0–100 health score with actionable findings.

Built as a full-stack portfolio project: FastAPI backend, async workers, React frontend, all wired together with Docker Compose.

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Backend API** | Python 3.11, FastAPI, SQLAlchemy (async + asyncpg), Alembic |
| **Workers** | Celery, Redis (broker + result backend) |
| **Database** | PostgreSQL 16 |
| **Frontend** | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| **Infrastructure** | Docker, Docker Compose |
| **CI/CD** | GitHub Actions |
| **Planned prod target** | AWS ECS Fargate, RDS, ElastiCache, S3, CloudFront |

---

## Quick Start

Requires **Docker Desktop** (or Docker Engine + Compose v2). No other dependencies.

```bash
git clone https://github.com/conquista41/healthcheck.git
cd healthcheck
bash demo_start.sh
```

That's it. The script copies the demo `.env`, builds all containers, waits for them to be healthy, and runs database migrations. Then open:

- **Frontend** → http://localhost:3000
- **API docs** → http://localhost:8000/docs

Click **Try Demo →** on the landing page to log in without a GitHub account.

```bash
# To stop everything:
docker compose down

# To tail logs:
docker compose logs -f
```

---

## Screenshots

> _Coming soon — dashboard, scan detail, and PDF report views._

---

## Architecture

```
Browser
  │
  ▼
Next.js (port 3000)
  │  REST + JWT
  ▼
FastAPI (port 8000)
  │
  ├── PostgreSQL  ← stores users, scans, results
  │
  └── Redis ──► Celery worker
                    │
                    ├── GitHub scanner
                    ├── Kubernetes scanner
                    └── Container scanner
```

**Request flow:**
1. User submits a scan → FastAPI creates a `Scan` row (status: `pending`) and dispatches a Celery task.
2. Worker picks up the task, runs the relevant scanner, writes results + a 0–100 score back to the `scans` table.
3. Frontend polls the scan detail endpoint every 3 seconds until status is `completed`, then renders the findings.

**Key paths:**

| Path | Role |
|---|---|
| `backend/app/api/v1/endpoints/` | Auth (GitHub OAuth + demo), users, scan CRUD |
| `backend/app/scanners/` | Stateless scanner modules — return structured dicts |
| `backend/app/workers/tasks.py` | Celery task that runs scanners and persists results |
| `backend/app/models/models.py` | SQLAlchemy ORM: `User`, `Scan`, `Report` |
| `frontend/src/app/` | Next.js App Router pages (landing, dashboard, scan detail) |
| `frontend/src/lib/api.ts` | Typed Axios client with JWT + refresh-token interceptors |

---

## Scan Types

| Type | What it checks |
|---|---|
| `github` | Branch protection, dangerous workflow triggers, exposed secrets, unpinned actions |
| `kubernetes` | Root containers, missing resource limits, `latest` image tags, absent liveness probes |
| `container` | Dockerfile root user, `ADD` vs `COPY`, unpinned base images, missing `HEALTHCHECK` |
| `cost` | _(stub)_ Idle resources, over-provisioned instances |
| `full` | All of the above combined |

---

## Roadmap

- [x] FastAPI skeleton + JWT auth
- [x] GitHub OAuth2 login
- [x] Demo mode (no GitHub account needed)
- [x] Scan models + Celery async workers
- [x] GitHub Actions scanner
- [x] Kubernetes manifest scanner
- [x] Dockerfile / container scanner
- [x] Next.js dashboard + scan detail UI
- [ ] PDF report generation (WeasyPrint)
- [ ] Stripe subscription + usage limits
- [ ] Cost analyzer scanner
- [ ] Terraform IaC for AWS
- [ ] Production deploy (ECS Fargate + RDS + CloudFront)

---

## Running Tests

```bash
# Tests run against a live PostgreSQL + Redis (matches CI)
docker compose exec api poetry run pytest --cov=app
```
