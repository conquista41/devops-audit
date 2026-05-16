"""
GitHub Scanner — analyzes GitHub Actions workflows and repo security.
Checks: secret exposure, workflow permissions, branch protection, dependency pinning.
"""
import httpx
import base64
import re
import yaml
from dataclasses import dataclass, field


@dataclass
class Issue:
    severity: str  # critical | warning | info
    title: str
    description: str
    file: str | None = None
    line: int | None = None
    fix: str | None = None


@dataclass
class ScanResult:
    score: int = 100
    issues: list[Issue] = field(default_factory=list)

    def add_issue(self, issue: Issue):
        self.issues.append(issue)
        if issue.severity == "critical":
            self.score = max(0, self.score - 20)
        elif issue.severity == "warning":
            self.score = max(0, self.score - 10)
        elif issue.severity == "info":
            self.score = max(0, self.score - 3)

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "summary": {
                "critical": sum(1 for i in self.issues if i.severity == "critical"),
                "warning": sum(1 for i in self.issues if i.severity == "warning"),
                "info": sum(1 for i 
                in self.issues if i.severity == "info"),
            },
            "issues": [
                {
                    "severity": i.severity,
                    "title": i.title,
                    "description": i.description,
                    "file": i.file,
                    "line": i.line,
                    "fix": i.fix,
                }
                for i in self.issues
            ],
        }


# Patterns that suggest hardcoded secrets
SECRET_PATTERNS = [
    (r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']?[\w!@#$%^&*]{8,}', "Possible hardcoded password"),
    (r'(?i)(api_key|apikey|api-key)\s*[:=]\s*["\']?[\w\-]{16,}', "Possible hardcoded API key"),
    (r'(?i)(secret|token)\s*[:=]\s*["\']?[\w\-]{16,}', "Possible hardcoded secret/token"),
    (r'AKIA[0-9A-Z]{16}', "AWS Access Key ID exposed"),
    (r'(?i)aws_secret_access_key\s*[:=]\s*["\']?[\w/+]{40}', "AWS Secret Key exposed"),
    (r'ghp_[a-zA-Z0-9]{36}', "GitHub Personal Access Token exposed"),
]


class GitHubScanner:
    def __init__(self, target: str, config: dict):
        # target = "owner/repo" or full URL
        self.repo = target.replace("https://github.com/", "").rstrip("/")
        self.token = config.get("github_token")
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"
        self.result = ScanResult()

    async def run(self) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            self.client = client
            await self._check_branch_protection()
            await self._check_workflows()
            await self._check_repo_settings()
        return self.result.to_dict()

    async def _check_branch_protection(self):
        resp = await self.client.get(
            f"https://api.github.com/repos/{self.repo}/branches/main",
            headers=self.headers,
        )
        if resp.status_code == 404:
            resp = await self.client.get(
                f"https://api.github.com/repos/{self.repo}/branches/master",
                headers=self.headers,
            )

        if resp.status_code != 200:
            return

        branch = resp.json()
        protection = branch.get("protection", {})

        if not branch.get("protected"):
            self.result.add_issue(Issue(
                severity="critical",
                title="Main branch is unprotected",
                description="Anyone with write access can force-push or delete the main branch.",
                fix="Enable branch protection rules: require PR reviews, status checks before merging.",
            ))
            return

        required_reviews = protection.get("required_pull_request_reviews")
        if not required_reviews:
            self.result.add_issue(Issue(
                severity="warning",
                title="No PR review requirement on main branch",
                description="Code can be merged to main without peer review.",
                fix="Require at least 1 approving review before merging.",
            ))

        if not protection.get("required_status_checks"):
            self.result.add_issue(Issue(
                severity="warning",
                title="No required status checks on main branch",
                description="CI checks are not enforced before merge.",
                fix="Add required status checks (CI tests, lint) to branch protection rules.",
            ))

    async def _check_workflows(self):
        resp = await self.client.get(
            f"https://api.github.com/repos/{self.repo}/contents/.github/workflows",
            headers=self.headers,
        )
        if resp.status_code != 200:
            self.result.add_issue(Issue(
                severity="info",
                title="No GitHub Actions workflows found",
                description="Consider adding CI/CD workflows for automated testing and deployment.",
                fix="Add a workflow file in .github/workflows/",
            ))
            return

        workflows = resp.json()
        for wf in workflows:
            if not wf["name"].endswith((".yml", ".yaml")):
                continue
            await self._analyze_workflow(wf["name"], wf["download_url"])

    async def _analyze_workflow(self, filename: str, download_url: str):
        resp = await self.client.get(download_url)
        if resp.status_code != 200:
            return

        content = resp.text
        lines = content.splitlines()

        # Check for secrets in plain text
        for i, line in enumerate(lines, 1):
            for pattern, title in SECRET_PATTERNS:
                if re.search(pattern, line):
                    self.result.add_issue(Issue(
                        severity="critical",
                        title=title,
                        description=f"Potential secret found in workflow file.",
                        file=f".github/workflows/{filename}",
                        line=i,
                        fix="Use GitHub Secrets (${{ secrets.MY_SECRET }}) instead of hardcoded values.",
                    ))

        # Parse YAML for deeper checks
        try:
            wf = yaml.safe_load(content)
            self._check_workflow_permissions(wf, filename)
            self._check_unpinned_actions(wf, filename)
            self._check_pull_request_target(wf, filename)
        except yaml.YAMLError:
            pass

    def _check_workflow_permissions(self, wf: dict, filename: str):
        permissions = wf.get("permissions")
        if permissions is None:
            self.result.add_issue(Issue(
                severity="warning",
                title="Workflow permissions not explicitly set",
                description=f"Workflows without explicit permissions default to read-all or write-all depending on org settings.",
                file=f".github/workflows/{filename}",
                fix="Add `permissions: read-all` at the top level, then grant only what's needed per job.",
            ))
        elif permissions == "write-all" or (isinstance(permissions, dict) and permissions.get("contents") == "write"):
            self.result.add_issue(Issue(
                severity="warning",
                title="Broad write permissions granted to workflow",
                description="Workflow has write access to repository contents.",
                file=f".github/workflows/{filename}",
                fix="Use least-privilege permissions. Only grant write access where strictly needed.",
            ))

    def _check_unpinned_actions(self, wf: dict, filename: str):
        jobs = wf.get("jobs", {})
        for job_name, job in jobs.items():
            steps = job.get("steps", [])
            for step in steps:
                uses = step.get("uses", "")
                if not uses or uses.startswith("."):
                    continue
                # Pinned to a SHA = safe. Tag/branch = risky.
                if "@" not in uses:
                    continue
                ref = uses.split("@")[1]
                if len(ref) != 40 or not all(c in "0123456789abcdef" for c in ref.lower()):
                    self.result.add_issue(Issue(
                        severity="info",
                        title=f"Action not pinned to SHA: {uses}",
                        description="Using a mutable tag means the action code can change without notice.",
                        file=f".github/workflows/{filename}",
                        fix=f"Pin to a full commit SHA: `{uses.split('@')[0]}@<sha>` for supply chain security.",
                    ))

    def _check_pull_request_target(self, wf: dict, filename: str):
        on = wf.get("on", {})
        if "pull_request_target" in (on if isinstance(on, dict) else {}):
            self.result.add_issue(Issue(
                severity="critical",
                title="Dangerous trigger: pull_request_target",
                description="`pull_request_target` runs with write permissions in the context of the base repo, even for forks. If the workflow checks out PR code, this can lead to secret exfiltration.",
                file=f".github/workflows/{filename}",
                fix="Avoid `pull_request_target` unless you fully understand the security implications. Prefer `pull_request`.",
            ))

    async def _check_repo_settings(self):
        resp = await self.client.get(
            f"https://api.github.com/repos/{self.repo}",
            headers=self.headers,
        )
        if resp.status_code != 200:
            return

        repo = resp.json()

        if not repo.get("private") and repo.get("has_wiki"):
            self.result.add_issue(Issue(
                severity="info",
                title="Wiki is enabled on a public repo",
                description="Public wikis can be edited by anyone (if not restricted). Review wiki access settings.",
                fix="Disable wiki if not used, or restrict edit access.",
            ))

        if repo.get("allow_forking") and not repo.get("private"):
            pass  # Fine for public repos

        if not repo.get("delete_branch_on_merge"):
            self.result.add_issue(Issue(
                severity="info",
                title="Branches not auto-deleted after merge",
                description="Merged branches accumulate and create confusion.",
                fix='Enable "Automatically delete head branches" in repository settings.',
            ))
