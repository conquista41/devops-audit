# HealthCheck.dev

DevOps audit tool — scan GitHub repos, Kubernetes configs, and Dockerfiles for security issues and misconfigurations. Get a PDF report in minutes.

## Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy (async), Celery, PostgreSQL, Redis
- **Frontend**: Next.js 14, TypeScript, Tailwind CSS
- **Infrastructure**: AWS ECS Fargate, RDS, ElastiCache, S3, CloudFront
- **IaC**: Terraform
- **CI/CD**: GitHub Actions

## Local development

### Prerequisites
- Docker & Docker Compose
- Python 3.11+ (for local backend dev without Docker)
- Node.js 20+

### 1. Clone and configure

```bash
git clone https://github.com/yourusername/healthcheck.git
cd healthcheck
cp backend/.env.example backend/.env
# Edit backend/.env with your GitHub OAuth credentials
```

### 2. Create GitHub OAuth App

Go to https://github.com/settings/applications/new:
- Application name: HealthCheck.dev (dev)
- Homepage URL: `http://localhost:3000`
- Callback URL: `http://localhost:8000/api/v1/auth/github/callback`

Copy Client ID and Secret to `backend/.env`.

### 3. Start services

```bash
docker-compose up -d db redis
# Wait for DB to be healthy, then run migrations:
cd backend && alembic upgrade head
# Start everything:
docker-compose up
```

API docs: http://localhost:8000/docs
Frontend: http://localhost:3000

### 4. Run tests

```bash
cd backend
poetry install
poetry run pytest -v
```

## Project structure

```
healthcheck/
├── backend/
│   └── app/
│       ├── api/v1/endpoints/   # FastAPI routes
│       ├── core/               # Config, DB, security
│       ├── models/             # SQLAlchemy models
│       ├── scanners/           # Scan modules (GitHub, K8s, Container)
│       ├── services/           # GitHub OAuth, PDF, S3
│       └── workers/            # Celery tasks
├── frontend/                   # Next.js app
├── infrastructure/
│   ├── docker/                 # Dockerfiles
│   └── terraform/              # AWS infrastructure
└── .github/workflows/          # CI/CD pipelines
```

## Scan types

| Type | What it checks |
|------|---------------|
| `github` | Branch protection, workflow security, secret exposure, action pinning |
| `kubernetes` | Resource limits, security context, image tags, liveness probes |
| `container` | Dockerfile best practices, root user, secret in ENV, image pinning |
| `cost` | (coming soon) Idle resources, right-sizing opportunities |
| `full` | All of the above |

## Roadmap

- [x] FastAPI skeleton + GitHub OAuth
- [x] Scan models + Celery workers
- [x] GitHub Actions scanner
- [x] Kubernetes scanner (basic)
- [x] Container/Dockerfile scanner
- [ ] PDF report generation
- [ ] Next.js dashboard
- [ ] Stripe subscription
- [ ] Cost analyzer module
- [ ] Terraform IaC
- [ ] Production deploy
