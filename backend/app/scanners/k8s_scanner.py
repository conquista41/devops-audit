"""
Kubernetes Scanner — finds and audits K8s manifests in a GitHub repository.

Accepts target = "owner/repo" or a full GitHub URL.
Walks the repo tree to discover all YAML files that contain Kubernetes
resource definitions (detected by apiVersion + kind fields), then applies
a comprehensive set of security and reliability checks against each workload.

Checks
  Security   — privileged containers, root UID, allowPrivilegeEscalation,
               readOnlyRootFilesystem, sensitive hostPath mounts,
               auto-mounted service account tokens
  Reliability — resource limits/requests, liveness/readiness probes,
                mutable image tags
"""
import base64
import re
import yaml
import httpx

from app.scanners.github_scanner import Issue, ScanResult


_WORKLOAD_KINDS = {
    "Deployment", "StatefulSet", "DaemonSet",
    "Job", "CronJob", "Pod", "ReplicaSet",
}

_SENSITIVE_HOST_PATHS = {"/", "/etc", "/proc", "/sys", "/var/run/docker.sock"}

# Directories that strongly signal K8s manifests even without content inspection
_K8S_DIRS = {
    "k8s", "deploy", "deployments", "manifests",
    "kubernetes", "helm", "infra", "overlays", "base", "charts",
}


class KubernetesScanner:
    def __init__(self, target: str, config: dict):
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
            manifests = await self._discover_manifests()
            if not manifests:
                self.result.add_issue(Issue(
                    severity="info",
                    title="No Kubernetes manifests found",
                    description="No YAML files with Kubernetes resource definitions were detected in the repository.",
                    fix="Add K8s manifests under a directory named k8s/, deploy/, or manifests/.",
                ))
                return self.result.to_dict()

            for path, content in manifests:
                self._audit_file(path, content)

        return self.result.to_dict()

    # ── Discovery ─────────────────────────────────────────────────────────────

    async def _discover_manifests(self) -> list[tuple[str, str]]:
        """Return (path, content) pairs for all K8s manifest files in the repo."""
        tree = await self._repo_tree()
        if tree is None:
            return []

        candidates: list[str] = []
        for item in tree:
            if item.get("type") != "blob":
                continue
            path: str = item["path"]
            if not path.endswith((".yaml", ".yml")):
                continue
            dirs = {p.lower() for p in path.split("/")[:-1]}
            if dirs & _K8S_DIRS:
                candidates.append(path)

        results: list[tuple[str, str]] = []
        for path in candidates:
            content = await self._fetch(path)
            if content and self._is_k8s_manifest(content):
                results.append((path, content))

        return results

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

    @staticmethod
    def _is_k8s_manifest(content: str) -> bool:
        try:
            return any(
                isinstance(doc, dict) and "apiVersion" in doc and "kind" in doc
                for doc in yaml.safe_load_all(content)
                if doc
            )
        except yaml.YAMLError:
            return False

    # ── Audit ─────────────────────────────────────────────────────────────────

    def _audit_file(self, path: str, content: str):
        try:
            docs = list(yaml.safe_load_all(content))
        except yaml.YAMLError:
            return
        for doc in docs:
            if isinstance(doc, dict) and doc.get("kind") in _WORKLOAD_KINDS:
                self._audit_workload(doc, path)

    def _audit_workload(self, doc: dict, path: str):
        kind = doc.get("kind", "")
        name = (doc.get("metadata") or {}).get("name", path)

        pod_spec = self._pod_spec(doc, kind)
        if not isinstance(pod_spec, dict):
            return

        pod_sc = pod_spec.get("securityContext") or {}
        containers = (pod_spec.get("containers") or []) + (pod_spec.get("initContainers") or [])

        for ctr in containers:
            if not isinstance(ctr, dict):
                continue
            label = f"{kind}/{name} → {ctr.get('name', '?')}"
            self._check_security_context(ctr, pod_sc, path, label)
            self._check_resources(ctr, path, label)
            self._check_image_tag(ctr, path, label)
            if kind not in ("Job", "CronJob"):
                self._check_probes(ctr, path, label)

        self._check_host_paths(pod_spec, path, f"{kind}/{name}")
        self._check_automount(pod_spec, path, f"{kind}/{name}")

    @staticmethod
    def _pod_spec(doc: dict, kind: str) -> dict:
        if kind == "Pod":
            return doc.get("spec") or {}
        if kind == "CronJob":
            return (
                doc.get("spec", {})
                .get("jobTemplate", {})
                .get("spec", {})
                .get("template", {})
                .get("spec", {})
            )
        return doc.get("spec", {}).get("template", {}).get("spec", {})

    # ── Per-container checks ──────────────────────────────────────────────────

    def _check_security_context(self, ctr: dict, pod_sc: dict, path: str, label: str):
        sc = ctr.get("securityContext") or {}

        if sc.get("privileged") is True:
            self.result.add_issue(Issue(
                severity="critical",
                title=f"Privileged container: {label}",
                description="Privileged containers bypass all Kubernetes security boundaries and gain host-level access.",
                file=path,
                fix="Remove `privileged: true`. Grant only the specific Linux capabilities the container needs.",
            ))

        non_root = sc.get("runAsNonRoot") or pod_sc.get("runAsNonRoot")
        uid = sc.get("runAsUser") if sc.get("runAsUser") is not None else pod_sc.get("runAsUser")
        if not non_root and (uid is None or uid == 0):
            self.result.add_issue(Issue(
                severity="critical",
                title=f"Container may run as root: {label}",
                description="UID 0 inside a container greatly increases the blast radius of a container escape.",
                file=path,
                fix="Set `securityContext.runAsNonRoot: true` and `securityContext.runAsUser: 1000`.",
            ))

        if sc.get("allowPrivilegeEscalation") is not False:
            self.result.add_issue(Issue(
                severity="warning",
                title=f"allowPrivilegeEscalation not disabled: {label}",
                description="A process inside the container can gain more privileges than its parent (e.g. via setuid binaries).",
                file=path,
                fix="Set `securityContext.allowPrivilegeEscalation: false`.",
            ))

        if not sc.get("readOnlyRootFilesystem"):
            self.result.add_issue(Issue(
                severity="warning",
                title=f"Writable root filesystem: {label}",
                description="A writable root filesystem allows attackers to modify binaries or persist backdoors.",
                file=path,
                fix="Set `securityContext.readOnlyRootFilesystem: true` and use emptyDir volumes for writable paths.",
            ))

    def _check_resources(self, ctr: dict, path: str, label: str):
        resources = ctr.get("resources") or {}
        limits = resources.get("limits") or {}
        requests = resources.get("requests") or {}

        if not limits.get("cpu") or not limits.get("memory"):
            self.result.add_issue(Issue(
                severity="warning",
                title=f"Missing resource limits: {label}",
                description="Without CPU/memory limits a single pod can starve all other workloads on the node.",
                file=path,
                fix="Set `resources.limits.cpu` and `resources.limits.memory` on every container.",
            ))

        if not requests.get("cpu") or not requests.get("memory"):
            self.result.add_issue(Issue(
                severity="info",
                title=f"Missing resource requests: {label}",
                description="Without resource requests the scheduler cannot make informed placement decisions.",
                file=path,
                fix="Set `resources.requests.cpu` and `resources.requests.memory`.",
            ))

    def _check_image_tag(self, ctr: dict, path: str, label: str):
        image = ctr.get("image") or ""
        if not image:
            return
        if ":" not in image or image.endswith(":latest"):
            self.result.add_issue(Issue(
                severity="warning",
                title=f"Image using mutable tag: {label}",
                description=f"`{image}` is not pinned to a specific version — silent upstream changes can cause unexpected rollouts.",
                file=path,
                fix="Pin to a digest: `image: myapp@sha256:<digest>`",
            ))

    def _check_probes(self, ctr: dict, path: str, label: str):
        if not ctr.get("livenessProbe"):
            self.result.add_issue(Issue(
                severity="warning",
                title=f"No livenessProbe: {label}",
                description="Without a liveness probe Kubernetes cannot restart containers that are stuck or deadlocked.",
                file=path,
                fix="Add a `livenessProbe` (httpGet, tcpSocket, or exec) to the container spec.",
            ))
        if not ctr.get("readinessProbe"):
            self.result.add_issue(Issue(
                severity="info",
                title=f"No readinessProbe: {label}",
                description="Without a readiness probe, traffic is sent to a container before it has finished starting up.",
                file=path,
                fix="Add a `readinessProbe` to the container spec.",
            ))

    # ── Pod-level checks ──────────────────────────────────────────────────────

    def _check_host_paths(self, pod_spec: dict, path: str, label: str):
        for vol in pod_spec.get("volumes") or []:
            if not isinstance(vol, dict):
                continue
            hp = (vol.get("hostPath") or {}).get("path", "")
            if hp in _SENSITIVE_HOST_PATHS:
                self.result.add_issue(Issue(
                    severity="critical",
                    title=f"Sensitive hostPath mount: {label} → {hp}",
                    description=f"Mounting `{hp}` from the host can allow a container escape or full host compromise.",
                    file=path,
                    fix="Avoid sensitive hostPath mounts. Use PersistentVolumeClaims instead.",
                ))

    def _check_automount(self, pod_spec: dict, path: str, label: str):
        if pod_spec.get("automountServiceAccountToken") is not False:
            self.result.add_issue(Issue(
                severity="info",
                title=f"Service account token auto-mounted: {label}",
                description="Auto-mounted tokens are injected into every pod and can be exploited if the pod is compromised.",
                file=path,
                fix="Set `automountServiceAccountToken: false` unless the pod explicitly calls the Kubernetes API.",
            ))
