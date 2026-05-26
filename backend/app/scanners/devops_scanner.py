"""
DevOps Scanner — discovers and audits all DevOps config files in a GitHub repo.

File types discovered via repo tree API:
  Dockerfiles           Dockerfile, Dockerfile.*
  Docker Compose        docker-compose*.yml
  Terraform             *.tf
  Kubernetes manifests  *.yaml in k8s/, deploy/, manifests/, kubernetes/, helm/
  GitLab CI             .gitlab-ci.yml
  Jenkinsfile           Jenkinsfile

Checks added here (Dockerfile analysis stays in ContainerScanner):
  Terraform     — hardcoded creds, public S3, open security groups,
                  unencrypted S3/RDS/EBS, missing resource tags
  Docker Compose — privileged mode, ports exposed to 0.0.0.0,
                   plaintext secrets in env vars, missing resource limits
  GitLab CI      — hardcoded secrets, Docker-in-Docker usage
  Jenkinsfile    — hardcoded credentials, curl|bash script injection
  K8s manifests  — privileged containers, root user, missing resource limits
"""
import re
import base64
import yaml
import httpx
from app.scanners.github_scanner import ScanResult, Issue

# ── Secret patterns shared across file types ──────────────────────────────────

_SECRET_RE = [
    (r'AKIA[0-9A-Z]{16}',                                          "Hardcoded AWS Access Key ID"),
    (r'(?i)aws_secret_access_key\s*[=:]\s*"[^"]{16,}"',           "Hardcoded AWS Secret Access Key"),
    (r'(?i)(password|passwd)\s*[=:]\s*"[^"]{4,}"',                "Hardcoded password"),
    (r'(?i)(secret|token)\s*[=:]\s*"[^"]{8,}"',                   "Hardcoded secret/token"),
    (r'(?i)(private_key|secret_key)\s*[=:]\s*"[^"]{8,}"',         "Hardcoded private key"),
]

_COMPOSE_SENSITIVE_KEY = re.compile(
    r'^\s*-?\s*(?P<key>PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE_KEY|ACCESS_KEY)'
    r'\s*[=:](?P<val>.*)$',
    re.IGNORECASE,
)

# Directories that are considered K8s manifest roots
_K8S_DIRS = {
    "k8s", "deploy", "deployments", "manifests",
    "kubernetes", "helm", "infra", "overlays", "base",
}

# K8s workload kinds that own a pod spec
_WORKLOAD_KINDS = {
    "Deployment", "StatefulSet", "DaemonSet",
    "Job", "CronJob", "Pod", "ReplicaSet",
}


class DevOpsScanner:
    def __init__(self, target: str, config: dict):
        # target = "owner/repo" or full GitHub URL
        self.repo = target.replace("https://github.com/", "").rstrip("/")
        self.token = config.get("github_token")
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"
        self.result = ScanResult()

    # ── Entry point ────────────────────────────────────────────────────────────

    async def run(self) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            self.client = client
            tree = await self._repo_tree()
            if tree is None:
                self.result.add_issue(Issue(
                    severity="info",
                    title="Repository tree unavailable",
                    description="Could not fetch the repository file tree. Check the token or repo name.",
                ))
                return self.result.to_dict()

            for item in tree:
                if item.get("type") != "blob":
                    continue
                await self._dispatch(item["path"])

        return self.result.to_dict()

    async def _dispatch(self, path: str):
        parts = path.split("/")
        fname = parts[-1]
        top_dir = parts[0] if len(parts) > 1 else ""

        if re.match(r'^docker-compose.*\.ya?ml$', fname, re.IGNORECASE):
            await self._check_compose(path)
        elif fname.endswith(".tf"):
            await self._check_terraform(path)
        elif fname in (".gitlab-ci.yml", ".gitlab-ci.yaml"):
            await self._check_gitlab_ci(path)
        elif fname == "Jenkinsfile":
            await self._check_jenkinsfile(path)
        elif re.match(r'^Dockerfile(\..+)?$', fname) and fname != "Dockerfile.frontend":
            await self._check_dockerfile(path)
        elif fname.endswith((".yaml", ".yml")) and top_dir in _K8S_DIRS:
            await self._check_k8s_manifest(path)

    # ── GitHub API helpers ─────────────────────────────────────────────────────

    async def _repo_tree(self) -> list | None:
        for branch in ("main", "master"):
            resp = await self.client.get(
                f"https://api.github.com/repos/{self.repo}/git/trees/{branch}?recursive=1",
                headers=self.headers,
            )
            if resp.status_code == 200:
                return resp.json().get("tree", [])
        return None

    async def _fetch(self, path: str) -> str | None:
        resp = await self.client.get(
            f"https://api.github.com/repos/{self.repo}/contents/{path}",
            headers=self.headers,
        )
        if resp.status_code != 200:
            return None
        raw = resp.json().get("content", "")
        if not raw:
            return None
        try:
            return base64.b64decode(raw).decode("utf-8", errors="replace")
        except Exception:
            return None

    # ── Dockerfile ─────────────────────────────────────────────────────────────

    async def _check_dockerfile(self, path: str):
        content = await self._fetch(path)
        if not content:
            return
        lines = content.splitlines()

        has_user = any(l.strip().upper().startswith("USER") for l in lines)
        if not has_user:
            self.result.add_issue(Issue(
                severity="critical",
                title="Dockerfile has no non-root USER",
                description="Container will run as root by default, widening the blast radius of any escape.",
                file=path,
                fix="Add `RUN useradd -r appuser` and `USER appuser` before the final CMD/ENTRYPOINT.",
            ))

        for i, line in enumerate(lines, 1):
            stripped = line.strip().upper()
            if stripped.startswith("FROM") and (
                ":latest" in line or (":" not in line.split()[-1] and "@" not in line)
            ):
                self.result.add_issue(Issue(
                    severity="warning",
                    title="Base image not pinned",
                    description="Mutable tags make builds non-reproducible and hide silent upstream changes.",
                    file=path,
                    line=i,
                    fix="Pin to a digest: `FROM python:3.11-slim@sha256:<digest>`",
                ))

            if stripped.startswith("ADD ") and "http" not in line.lower():
                self.result.add_issue(Issue(
                    severity="info",
                    title="Prefer COPY over ADD",
                    description="ADD has implicit tar-extraction and URL-fetch behaviours; COPY is predictable.",
                    file=path,
                    line=i,
                    fix="Replace `ADD` with `COPY` unless you specifically need ADD's extra features.",
                ))

            if re.search(r'(?i)ENV\s+(PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE_KEY)\s*=', line):
                self.result.add_issue(Issue(
                    severity="critical",
                    title="Secret baked into image via ENV",
                    description="ENV values are stored in image layers and visible via `docker inspect`.",
                    file=path,
                    line=i,
                    fix="Pass secrets at runtime or use Docker BuildKit's `--secret` flag.",
                ))

    # ── Docker Compose ─────────────────────────────────────────────────────────

    async def _check_compose(self, path: str):
        content = await self._fetch(path)
        if not content:
            return
        lines = content.splitlines()

        try:
            compose = yaml.safe_load(content)
        except yaml.YAMLError:
            return

        if not isinstance(compose, dict):
            return

        for svc_name, svc in (compose.get("services") or {}).items():
            if not isinstance(svc, dict):
                continue

            # privileged: true
            if svc.get("privileged") is True:
                self.result.add_issue(Issue(
                    severity="critical",
                    title=f"Service '{svc_name}' runs privileged",
                    description="Privileged containers share the host kernel namespace and can escape to the host.",
                    file=path,
                    line=_find_line(lines, "privileged: true"),
                    fix="Remove `privileged: true`. Use `cap_add` for specific capabilities only.",
                ))

            # Ports bound to all interfaces
            for port_entry in svc.get("ports") or []:
                port_str = str(port_entry)
                # "HOST:CONTAINER" without IP → 0.0.0.0 by default
                if re.match(r'^\d+:\d+$', port_str) or port_str.startswith("0.0.0.0:"):
                    self.result.add_issue(Issue(
                        severity="warning",
                        title=f"Service '{svc_name}' port {port_str} exposed to all interfaces",
                        description="Binding to 0.0.0.0 makes the port reachable from every network interface.",
                        file=path,
                        line=_find_line(lines, port_str),
                        fix=f"Restrict to loopback for local services: `127.0.0.1:{port_str}`",
                    ))

            # Secrets in environment variables
            env = svc.get("environment") or []
            env_items = list(env.items()) if isinstance(env, dict) else [(e, None) for e in env]
            for key_raw, val in env_items:
                key_str = str(key_raw)
                val_str = str(val) if val is not None else ""
                m = _COMPOSE_SENSITIVE_KEY.match(key_str)
                if m:
                    # Skip if value is a variable reference or empty
                    if not val_str or re.match(r'^\$\{?\w+\}?$', val_str.strip()):
                        continue
                    self.result.add_issue(Issue(
                        severity="warning",
                        title=f"Possible plaintext secret in '{svc_name}' env: {m.group('key')}",
                        description="Hardcoded secrets in Compose files are committed to source control.",
                        file=path,
                        line=_find_line(lines, key_str),
                        fix="Reference a variable: `PASSWORD=${DB_PASSWORD}` and keep values in an untracked .env file.",
                    ))

            # Missing resource limits (deploy.resources.limits)
            limits = (
                (svc.get("deploy") or {})
                .get("resources", {})
                .get("limits", {})
            )
            if not limits:
                self.result.add_issue(Issue(
                    severity="info",
                    title=f"Service '{svc_name}' has no resource limits",
                    description="Without CPU/memory limits a runaway container can starve all other services on the host.",
                    file=path,
                    fix=(
                        f"Add to '{svc_name}':\n"
                        "  deploy:\n"
                        "    resources:\n"
                        "      limits:\n"
                        "        cpus: '0.5'\n"
                        "        memory: 512M"
                    ),
                ))

    # ── Terraform ──────────────────────────────────────────────────────────────

    async def _check_terraform(self, path: str):
        content = await self._fetch(path)
        if not content:
            return
        lines = content.splitlines()

        # Hardcoded credentials
        for i, line in enumerate(lines, 1):
            for pattern, title in _SECRET_RE:
                if re.search(pattern, line):
                    self.result.add_issue(Issue(
                        severity="critical",
                        title=f"Terraform: {title}",
                        description="Secrets committed to .tf files are stored in version control and Terraform state.",
                        file=path,
                        line=i,
                        fix=(
                            "Use `variable` blocks with `sensitive = true` and pass values via TF_VAR_ env vars, "
                            "or fetch from AWS Secrets Manager with a `data` source."
                        ),
                    ))

        # Public S3 bucket (acl = "public-read" / "public-read-write")
        for i, line in enumerate(lines, 1):
            if re.search(r'acl\s*=\s*"public-read', line, re.IGNORECASE):
                self.result.add_issue(Issue(
                    severity="critical",
                    title="S3 bucket ACL is public",
                    description="Bucket contents are accessible to anyone on the internet.",
                    file=path,
                    line=i,
                    fix="Remove the `acl` argument, enable S3 Block Public Access, and use bucket policies for controlled sharing.",
                ))

        # Security group open to internet
        for i, line in enumerate(lines, 1):
            if re.search(r'cidr_blocks\s*=\s*\[.*"0\.0\.0\.0/0"', line):
                self.result.add_issue(Issue(
                    severity="critical",
                    title="Security group allows 0.0.0.0/0 ingress",
                    description="Inbound rule allows traffic from any IP on the internet.",
                    file=path,
                    line=i,
                    fix="Restrict `cidr_blocks` to known IP ranges. Only expose ports that must be publicly accessible.",
                ))
            if re.search(r'ipv6_cidr_blocks\s*=\s*\[.*"::/0"', line):
                self.result.add_issue(Issue(
                    severity="critical",
                    title="Security group allows ::/0 IPv6 ingress",
                    description="Inbound rule allows traffic from any IPv6 address.",
                    file=path,
                    line=i,
                    fix="Restrict `ipv6_cidr_blocks` to known prefixes.",
                ))

        # Unencrypted resources
        self._tf_encryption(lines, path)

        # Missing tags (info, cap at 3 findings per file to avoid noise)
        self._tf_tags(content, path)

    def _tf_encryption(self, lines: list[str], path: str):
        content = "\n".join(lines)

        if "aws_s3_bucket" in content and "server_side_encryption_configuration" not in content:
            self.result.add_issue(Issue(
                severity="warning",
                title="S3 bucket may lack server-side encryption",
                description="No `server_side_encryption_configuration` block found alongside an S3 bucket resource.",
                file=path,
                fix="Add an `aws_s3_bucket_server_side_encryption_configuration` resource with AES256 or aws:kms.",
            ))

        for i, line in enumerate(lines, 1):
            if re.search(r'resource\s+"aws_db_instance"', line) or re.search(r'resource\s+"aws_rds_cluster"', line):
                block = "\n".join(lines[i - 1: i + 40])
                if "storage_encrypted" not in block:
                    self.result.add_issue(Issue(
                        severity="warning",
                        title="RDS instance missing storage_encrypted",
                        description="Database storage is not encrypted at rest.",
                        file=path,
                        line=i,
                        fix="Add `storage_encrypted = true` to the aws_db_instance / aws_rds_cluster resource.",
                    ))
                elif re.search(r'storage_encrypted\s*=\s*false', block):
                    self.result.add_issue(Issue(
                        severity="critical",
                        title="RDS storage encryption explicitly disabled",
                        description="`storage_encrypted = false` stores all database data unencrypted.",
                        file=path,
                        line=i,
                        fix="Set `storage_encrypted = true`.",
                    ))
                break  # one finding per file is enough

        for i, line in enumerate(lines, 1):
            if re.search(r'resource\s+"aws_ebs_volume"', line):
                block = "\n".join(lines[i - 1: i + 20])
                if "encrypted" not in block:
                    self.result.add_issue(Issue(
                        severity="warning",
                        title="EBS volume missing encryption",
                        description="EBS volume data is not encrypted at rest.",
                        file=path,
                        line=i,
                        fix="Add `encrypted = true` to the aws_ebs_volume resource.",
                    ))
                break

    def _tf_tags(self, content: str, path: str):
        findings = 0
        for match in re.finditer(
            r'^resource\s+"(?P<type>aws_\w+)"\s+"(?P<name>\w+)"\s*\{',
            content,
            re.MULTILINE,
        ):
            if findings >= 3:
                break
            block_start_line = content[: match.start()].count("\n") + 1
            block_text = content[match.start():].split("\n")[:60]
            if "tags" not in "\n".join(block_text):
                self.result.add_issue(Issue(
                    severity="info",
                    title=f"Resource '{match.group('name')}' ({match.group('type')}) missing tags",
                    description="Untagged AWS resources are difficult to track for cost allocation and compliance audits.",
                    file=path,
                    line=block_start_line,
                    fix="Add a `tags` block with at minimum: Name, Environment, and Project.",
                ))
                findings += 1

    # ── GitLab CI ──────────────────────────────────────────────────────────────

    async def _check_gitlab_ci(self, path: str):
        content = await self._fetch(path)
        if not content:
            return
        lines = content.splitlines()

        for i, line in enumerate(lines, 1):
            for pattern, title in _SECRET_RE:
                if re.search(pattern, line):
                    self.result.add_issue(Issue(
                        severity="critical",
                        title=f"GitLab CI: {title}",
                        description="Secrets committed to CI config are visible to all contributors with repo access.",
                        file=path,
                        line=i,
                        fix="Use GitLab CI/CD Variables (Settings → CI/CD → Variables) with the 'Masked' flag.",
                    ))

        try:
            ci = yaml.safe_load(content)
        except yaml.YAMLError:
            return

        if not isinstance(ci, dict):
            return

        for job_name, job in ci.items():
            if not isinstance(job, dict):
                continue
            if "docker:dind" in (job.get("services") or []):
                self.result.add_issue(Issue(
                    severity="warning",
                    title=f"Job '{job_name}' uses Docker-in-Docker",
                    description="DinD requires privileged mode, granting the container full host kernel access.",
                    file=path,
                    fix="Use Kaniko or Buildah as a daemonless, rootless alternative to Docker-in-Docker.",
                ))
            # Plaintext variables inside the job
            for key, val in (job.get("variables") or {}).items():
                if _COMPOSE_SENSITIVE_KEY.match(str(key)) and val and not str(val).startswith("$"):
                    self.result.add_issue(Issue(
                        severity="warning",
                        title=f"Possible plaintext secret in job '{job_name}' variable: {key}",
                        description="Job-level variables are stored in the repository and visible in CI logs.",
                        file=path,
                        fix=f"Move {key} to a protected/masked CI/CD variable.",
                    ))

    # ── Jenkinsfile ────────────────────────────────────────────────────────────

    async def _check_jenkinsfile(self, path: str):
        content = await self._fetch(path)
        if not content:
            return
        lines = content.splitlines()

        for i, line in enumerate(lines, 1):
            if re.search(r'(?i)(password|secret|token|apikey)\s*=\s*["\'][^"\']{4,}["\']', line):
                self.result.add_issue(Issue(
                    severity="critical",
                    title="Hardcoded credential in Jenkinsfile",
                    description="Credentials in Jenkinsfiles are committed to source control and visible in build logs.",
                    file=path,
                    line=i,
                    fix="Use the Jenkins Credentials Store and `withCredentials([...])` bindings.",
                ))
            if re.search(r'sh\s+["\'].*curl.*\|.*bash', line):
                self.result.add_issue(Issue(
                    severity="warning",
                    title="curl | bash pattern in Jenkinsfile",
                    description="Piping curl output directly to bash executes arbitrary remote code without verification.",
                    file=path,
                    line=i,
                    fix="Download the script, verify its checksum, then execute it as a separate step.",
                ))

    # ── Kubernetes manifests ───────────────────────────────────────────────────

    async def _check_k8s_manifest(self, path: str):
        content = await self._fetch(path)
        if not content:
            return

        try:
            docs = list(yaml.safe_load_all(content))
        except yaml.YAMLError:
            return

        for doc in docs:
            if not isinstance(doc, dict) or doc.get("kind") not in _WORKLOAD_KINDS:
                continue
            self._k8s_audit_workload(doc, path)

    def _k8s_audit_workload(self, doc: dict, path: str):
        kind = doc.get("kind", "")
        name = (doc.get("metadata") or {}).get("name", path)

        if kind == "Pod":
            pod_spec = doc.get("spec") or {}
        elif kind == "CronJob":
            pod_spec = (
                doc.get("spec", {})
                .get("jobTemplate", {})
                .get("spec", {})
                .get("template", {})
                .get("spec", {})
            )
        else:
            pod_spec = (
                doc.get("spec", {})
                .get("template", {})
                .get("spec", {})
            )

        if not isinstance(pod_spec, dict):
            return

        for container in pod_spec.get("containers") or []:
            cname = container.get("name", "?")
            sc = container.get("securityContext") or {}

            if sc.get("privileged") is True:
                self.result.add_issue(Issue(
                    severity="critical",
                    title=f"Container '{cname}' in {kind} '{name}' is privileged",
                    description="Privileged containers can escape to the host kernel.",
                    file=path,
                    fix="Remove `privileged: true`. Use `capabilities.add` for specific kernel capabilities.",
                ))

            if not sc.get("runAsNonRoot") and not sc.get("runAsUser"):
                self.result.add_issue(Issue(
                    severity="warning",
                    title=f"Container '{cname}' in {kind} '{name}' may run as root",
                    description="No runAsNonRoot or runAsUser constraint; container defaults to UID 0.",
                    file=path,
                    fix="Set `securityContext.runAsNonRoot: true` and `runAsUser: 1000`.",
                ))

            if not (container.get("resources") or {}).get("limits"):
                self.result.add_issue(Issue(
                    severity="warning",
                    title=f"Container '{cname}' in {kind} '{name}' has no resource limits",
                    description="Unbounded containers can exhaust all node resources.",
                    file=path,
                    fix="Add `resources.limits.cpu` and `resources.limits.memory`.",
                ))


# ── Module-level helper ────────────────────────────────────────────────────────

def _find_line(lines: list[str], needle: str) -> int | None:
    if needle is None:
        return None
    for i, line in enumerate(lines, 1):
        if needle in line:
            return i
    return None
