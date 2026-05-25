"""Pre-built realistic scan results used in DEMO_MODE to avoid real API calls."""


def get_demo_results(scan_type: str, target: str) -> dict:
    generators = {
        "github": _github_results,
        "kubernetes": _kubernetes_results,
        "container": _container_results,
        "cost": _cost_results,
        "full": _full_results,
    }
    return generators.get(scan_type, _github_results)(target)


def _github_results(target: str) -> dict:
    return {
        "score": 62,
        "summary": {"critical": 2, "warning": 3, "info": 2},
        "issues": [
            {
                "severity": "critical",
                "title": "Dangerous trigger: pull_request_target",
                "description": (
                    f"`pull_request_target` in {target}/.github/workflows/ci.yml runs with "
                    "write permissions even for fork PRs, enabling secret exfiltration."
                ),
                "file": ".github/workflows/ci.yml",
                "line": 3,
                "fix": "Replace `pull_request_target` with `pull_request` unless you need write permissions from a fork.",
            },
            {
                "severity": "critical",
                "title": "AWS Access Key ID exposed",
                "description": "A hardcoded AWS_ACCESS_KEY_ID pattern was found in a workflow file.",
                "file": ".github/workflows/deploy.yml",
                "line": 47,
                "fix": "Rotate the key in AWS IAM immediately and store it as ${{ secrets.AWS_ACCESS_KEY_ID }}.",
            },
            {
                "severity": "warning",
                "title": "Main branch is unprotected",
                "description": "Anyone with write access can force-push directly to main without review.",
                "file": None,
                "line": None,
                "fix": "Enable branch protection: require at least 1 PR review and passing CI checks before merge.",
            },
            {
                "severity": "warning",
                "title": "Workflow permissions not explicitly set",
                "description": "Workflows inherit default org-level permissions, which may be write-all.",
                "file": ".github/workflows/ci.yml",
                "line": 1,
                "fix": "Add `permissions: read-all` at the workflow root, then grant specific write permissions per job.",
            },
            {
                "severity": "warning",
                "title": "Action not pinned to SHA: actions/checkout@v4",
                "description": "Using a mutable tag means the action code can change between runs without notice.",
                "file": ".github/workflows/ci.yml",
                "line": 14,
                "fix": "Pin to a full commit SHA: `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683`",
            },
            {
                "severity": "info",
                "title": "Wiki is enabled on a public repo",
                "description": "Public wikis can be edited by any logged-in GitHub user unless restricted.",
                "file": None,
                "line": None,
                "fix": "Disable the wiki under Settings → Features, or restrict edit access to collaborators only.",
            },
            {
                "severity": "info",
                "title": "Branches not auto-deleted after merge",
                "description": "Merged branches accumulate and create noise in the repository.",
                "file": None,
                "line": None,
                "fix": 'Enable "Automatically delete head branches" under Settings → General.',
            },
        ],
    }


def _kubernetes_results(target: str) -> dict:
    return {
        "score": 47,
        "summary": {"critical": 1, "warning": 2, "info": 1},
        "issues": [
            {
                "severity": "critical",
                "title": "Containers running as root",
                "description": (
                    "3 Deployments do not set securityContext.runAsNonRoot, "
                    "defaulting to root (UID 0) inside the container."
                ),
                "file": "deployments/api.yaml",
                "line": 28,
                "fix": "Set securityContext.runAsNonRoot: true and securityContext.runAsUser: 1000 on each container.",
            },
            {
                "severity": "warning",
                "title": "Resource limits not set on containers",
                "description": "5 containers have no CPU or memory limits. A runaway pod can exhaust the entire node.",
                "file": "deployments/worker.yaml",
                "line": 19,
                "fix": "Add resources.limits.cpu and resources.limits.memory to every container spec.",
            },
            {
                "severity": "warning",
                "title": "Images using 'latest' tag",
                "description": "2 Deployments reference images tagged ':latest', making rollbacks unreliable.",
                "file": "deployments/api.yaml",
                "line": 22,
                "fix": "Pin images to an immutable digest: `image: myapp@sha256:<digest>`",
            },
            {
                "severity": "info",
                "title": "Liveness/readiness probes not configured",
                "description": "4 containers have no probes. Kubernetes cannot auto-restart unhealthy pods.",
                "file": "deployments/frontend.yaml",
                "line": 15,
                "fix": "Add livenessProbe and readinessProbe to each container.",
            },
        ],
    }


def _container_results(target: str) -> dict:
    return {
        "score": 55,
        "summary": {"critical": 1, "warning": 1, "info": 2},
        "issues": [
            {
                "severity": "critical",
                "title": "Dockerfile does not set a non-root USER",
                "description": "The final stage has no USER instruction; the process runs as root (UID 0).",
                "file": "Dockerfile",
                "line": None,
                "fix": "Add `RUN useradd -r appuser && USER appuser` before the CMD/ENTRYPOINT.",
            },
            {
                "severity": "warning",
                "title": "Base image not pinned to a specific tag",
                "description": "`FROM python:3.11` resolves to the latest patch. Different CI runs may pull different images.",
                "file": "Dockerfile",
                "line": 1,
                "fix": "Pin to a digest: `FROM python:3.11-slim@sha256:<digest>` for reproducible builds.",
            },
            {
                "severity": "info",
                "title": "Use COPY instead of ADD",
                "description": "ADD has implicit tar-extraction and URL-fetch behaviors. COPY is more predictable.",
                "file": "Dockerfile",
                "line": 9,
                "fix": "Replace `ADD . /app` with `COPY . /app` unless you specifically need ADD's extra capabilities.",
            },
            {
                "severity": "info",
                "title": "No HEALTHCHECK instruction",
                "description": "Without HEALTHCHECK, Docker and orchestrators cannot detect a stuck container.",
                "file": "Dockerfile",
                "line": None,
                "fix": "Add `HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1` before CMD.",
            },
        ],
    }


def _cost_results(target: str) -> dict:
    return {
        "score": 70,
        "summary": {"critical": 0, "warning": 2, "info": 3},
        "issues": [
            {
                "severity": "warning",
                "title": "Over-provisioned ECS task CPU",
                "description": "API task is allocated 1 vCPU but average utilization is 8%. Estimated waste: $42/month.",
                "file": None,
                "line": None,
                "fix": "Reduce cpu to 256 or 512. Monitor p99 for one week before reducing further.",
            },
            {
                "severity": "warning",
                "title": "RDS dev instance running 24/7",
                "description": "Dev RDS instance (db.t3.medium) has no stop schedule. Estimated waste: $55/month.",
                "file": None,
                "line": None,
                "fix": "Add an RDS scheduled start/stop, or switch to Aurora Serverless v2 for dev.",
            },
            {
                "severity": "info",
                "title": "S3 bucket missing lifecycle policy",
                "description": "The reports bucket has no expiry rule; old objects accumulate indefinitely.",
                "file": None,
                "line": None,
                "fix": "Add a lifecycle rule to expire objects older than 90 days or move them to Glacier.",
            },
            {
                "severity": "info",
                "title": "CloudWatch log retention not set",
                "description": "3 log groups have no retention policy and will store logs forever.",
                "file": None,
                "line": None,
                "fix": "Set a 30–90 day retention policy on all log groups.",
            },
            {
                "severity": "info",
                "title": "NAT Gateway in single AZ",
                "description": "All outbound traffic routes through one NAT Gateway — single point of failure.",
                "file": None,
                "line": None,
                "fix": "Add one NAT Gateway per AZ, or use NAT instances for lower cost.",
            },
        ],
    }


def _full_results(target: str) -> dict:
    gh = _github_results(target)
    k8s = _kubernetes_results(target)
    container = _container_results(target)
    all_issues = gh["issues"] + k8s["issues"] + container["issues"]
    return {
        "score": int((gh["score"] + k8s["score"] + container["score"]) / 3),
        "summary": {
            "critical": sum(1 for i in all_issues if i["severity"] == "critical"),
            "warning": sum(1 for i in all_issues if i["severity"] == "warning"),
            "info": sum(1 for i in all_issues if i["severity"] == "info"),
        },
        "issues": all_issues,
    }
