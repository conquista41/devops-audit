"""Pre-built realistic scan results used in DEMO_MODE to avoid real API calls."""


def get_demo_results(scan_type: str, target: str) -> dict:
    generators = {
        "github": _github_results,
        "kubernetes": _kubernetes_results,
        "container": _container_results,
        "devops": _devops_results,
        "cost": _cost_results,
        "full": _full_results,
    }
    return generators.get(scan_type, _github_results)(target)


def _github_results(target: str) -> dict:
    # Reflects actual repo state: permissions: contents: read is set,
    # actions are pinned to SHAs, no pull_request_target trigger.
    return {
        "score": 84,
        "summary": {"critical": 0, "warning": 1, "info": 2},
        "issues": [
            {
                "severity": "warning",
                "title": "Main branch is unprotected",
                "description": "Anyone with write access can force-push directly to main without review.",
                "file": None,
                "line": None,
                "fix": "Enable branch protection: require at least 1 PR review and passing CI checks before merge.",
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
    # Reflects k8s/ manifests: all three Deployments set runAsNonRoot,
    # resource limits/requests, liveness+readiness probes, and
    # automountServiceAccountToken: false.
    # Remaining: images reference ':latest' tags — needs digest pinning.
    return {
        "score": 87,
        "summary": {"critical": 0, "warning": 1, "info": 0},
        "issues": [
            {
                "severity": "warning",
                "title": "Images using 'latest' tag",
                "description": "All 3 Deployments reference images tagged ':latest', making rollbacks unreliable.",
                "file": "k8s/api.yaml",
                "line": 22,
                "fix": "Pin images to an immutable digest: `image: ghcr.io/conquista41/devops-audit-backend@sha256:<digest>`",
            },
        ],
    }


def _container_results(target: str) -> dict:
    # Reflects infrastructure/docker/Dockerfile.backend:
    # - USER app is set (non-root) ✓
    # - COPY used throughout ✓
    # - Base image pinned to SHA256 digest ✓
    # - HEALTHCHECK added ✓
    return {
        "score": 97,
        "summary": {"critical": 0, "warning": 0, "info": 1},
        "issues": [
            {
                "severity": "info",
                "title": "Consider multi-stage build to reduce image size",
                "description": "The backend image installs build-essential and other compile-time tools that are not needed at runtime, increasing the final image size.",
                "file": "infrastructure/docker/Dockerfile.backend",
                "line": 5,
                "fix": "Use a multi-stage build: compile/install in a `builder` stage, then COPY only the installed packages into a clean `python:3.11-slim` final stage.",
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


def _devops_results(target: str) -> dict:
    # docker-compose issues removed: ports are now bound to 127.0.0.1
    # and resource limits have been added to api and worker services.
    return {
        "score": 71,
        "summary": {"critical": 3, "warning": 1, "info": 2},
        "issues": [
            {
                "severity": "critical",
                "title": "Terraform: Hardcoded AWS Access Key ID",
                "description": "An AKIA* key was found hardcoded in infrastructure/main.tf.",
                "file": "infrastructure/main.tf",
                "line": 14,
                "fix": "Rotate the key immediately, then use a `variable` with `sensitive = true` or an IAM role.",
            },
            {
                "severity": "critical",
                "title": "S3 bucket ACL is public",
                "description": "`acl = \"public-read\"` on the reports bucket exposes all objects to the internet.",
                "file": "infrastructure/s3.tf",
                "line": 8,
                "fix": "Remove the `acl` argument and enable S3 Block Public Access on the bucket.",
            },
            {
                "severity": "critical",
                "title": "Security group allows 0.0.0.0/0 ingress",
                "description": "The API security group accepts inbound traffic from any IP on port 5432 (PostgreSQL).",
                "file": "infrastructure/security_groups.tf",
                "line": 22,
                "fix": "Restrict `cidr_blocks` to the application tier's private CIDR range.",
            },
            {
                "severity": "warning",
                "title": "RDS instance missing storage_encrypted",
                "description": "The production RDS instance does not set `storage_encrypted = true`.",
                "file": "infrastructure/rds.tf",
                "line": 5,
                "fix": "Add `storage_encrypted = true` to the aws_db_instance resource.",
            },
            {
                "severity": "info",
                "title": "Resource 'api_bucket' (aws_s3_bucket) missing tags",
                "description": "S3 bucket has no tags — difficult to track in cost reports.",
                "file": "infrastructure/s3.tf",
                "line": 3,
                "fix": "Add tags: Name, Environment, and Project.",
            },
            {
                "severity": "info",
                "title": "Resource 'app_server' (aws_instance) missing tags",
                "description": "EC2 instance has no tags — cannot be filtered in the AWS console by project.",
                "file": "infrastructure/ec2.tf",
                "line": 1,
                "fix": "Add tags: Name, Environment, and Project.",
            },
        ],
    }


def _full_results(target: str) -> dict:
    gh = _github_results(target)
    k8s = _kubernetes_results(target)
    container = _container_results(target)
    devops = _devops_results(target)
    all_issues = gh["issues"] + k8s["issues"] + container["issues"] + devops["issues"]
    return {
        "score": int((gh["score"] + k8s["score"] + container["score"] + devops["score"]) / 4),
        "summary": {
            "critical": sum(1 for i in all_issues if i["severity"] == "critical"),
            "warning": sum(1 for i in all_issues if i["severity"] == "warning"),
            "info": sum(1 for i in all_issues if i["severity"] == "info"),
        },
        "issues": all_issues,
    }
