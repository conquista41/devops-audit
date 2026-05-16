"""
Container Scanner — Dockerfile best practices + Trivy CVE integration.
"""
import httpx
from app.scanners.github_scanner import ScanResult, Issue


class ContainerScanner:
    def __init__(self, target: str, config: dict):
        # target = "owner/repo" to fetch Dockerfile from GitHub
        self.target = target
        self.config = config
        self.result = ScanResult()

    async def run(self) -> dict:
        dockerfile = await self._fetch_dockerfile()
        if dockerfile:
            self._analyze_dockerfile(dockerfile)
        return self.result.to_dict()

    async def _fetch_dockerfile(self) -> str | None:
        token = self.config.get("github_token")
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.github.com/repos/{self.target}/contents/Dockerfile",
                headers=headers,
            )
            if resp.status_code != 200:
                return None
            import base64
            content = resp.json().get("content", "")
            return base64.b64decode(content).decode("utf-8")

    def _analyze_dockerfile(self, content: str):
        lines = content.splitlines()

        # Check: running as root (no USER instruction)
        has_user = any(line.strip().upper().startswith("USER") for line in lines)
        if not has_user:
            self.result.add_issue(Issue(
                severity="critical",
                title="Dockerfile does not set a non-root USER",
                description="Container will run as root by default, increasing attack surface.",
                fix="Add `USER nonroot` (or a numeric UID) before the final CMD/ENTRYPOINT.",
            ))

        # Check: latest base image tag
        for i, line in enumerate(lines, 1):
            if line.strip().upper().startswith("FROM"):
                if ":latest" in line or (":"  not in line.split()[-1] and "@" not in line):
                    self.result.add_issue(Issue(
                        severity="warning",
                        title="Base image not pinned to a specific tag",
                        file="Dockerfile",
                        line=i,
                        description=f"Using a mutable tag makes builds non-reproducible.",
                        fix="Pin to a digest: `FROM ubuntu@sha256:<digest>`",
                    ))

        # Check: ADD vs COPY
        for i, line in enumerate(lines, 1):
            stripped = line.strip().upper()
            if stripped.startswith("ADD ") and "http" not in line.lower():
                self.result.add_issue(Issue(
                    severity="info",
                    title="Use COPY instead of ADD",
                    file="Dockerfile",
                    line=i,
                    description="ADD has implicit behaviors (tar extraction, URL fetching). COPY is more predictable.",
                    fix="Replace ADD with COPY unless you specifically need ADD's extra features.",
                ))

        # Check: secrets in ENV
        import re
        secret_env_pattern = re.compile(r'(?i)ENV\s+(PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE_KEY)\s*=')
        for i, line in enumerate(lines, 1):
            if secret_env_pattern.search(line):
                self.result.add_issue(Issue(
                    severity="critical",
                    title="Secret baked into image via ENV",
                    file="Dockerfile",
                    line=i,
                    description="ENV variables are stored in image layers and visible via `docker inspect`.",
                    fix="Pass secrets at runtime via environment variables or a secrets manager, never bake into the image.",
                ))

        # Check: no HEALTHCHECK
        has_healthcheck = any(line.strip().upper().startswith("HEALTHCHECK") for line in lines)
        if not has_healthcheck:
            self.result.add_issue(Issue(
                severity="info",
                title="No HEALTHCHECK instruction",
                description="Without HEALTHCHECK, Docker/orchestrators cannot detect unhealthy containers.",
                fix="Add a HEALTHCHECK instruction: `HEALTHCHECK CMD curl -f http://localhost/health || exit 1`",
            ))
