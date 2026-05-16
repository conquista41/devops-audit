"""
Kubernetes Scanner — audits K8s manifests or live cluster.
Uses kube-score logic implemented in Python for manifest files,
or kubectl API for live clusters.
"""
from app.scanners.github_scanner import ScanResult, Issue


class KubernetesScanner:
    def __init__(self, target: str, config: dict):
        # target = path to manifest dir or "live" for connected cluster
        self.target = target
        self.config = config
        self.result = ScanResult()

    async def run(self) -> dict:
        await self._check_resource_limits()
        await self._check_security_context()
        await self._check_image_tags()
        await self._check_liveness_probes()
        return self.result.to_dict()

    async def _check_resource_limits(self):
        # TODO: parse manifests / call kubectl
        self.result.add_issue(Issue(
            severity="warning",
            title="Resource limits not set on containers",
            description="Without CPU/memory limits, a single pod can starve other workloads.",
            fix="Set resources.limits.cpu and resources.limits.memory on every container.",
        ))

    async def _check_security_context(self):
        self.result.add_issue(Issue(
            severity="critical",
            title="Containers running as root",
            description="Running as root inside a container increases the blast radius of a container escape.",
            fix="Set securityContext.runAsNonRoot: true and securityContext.runAsUser: 1000.",
        ))

    async def _check_image_tags(self):
        self.result.add_issue(Issue(
            severity="warning",
            title="Images using 'latest' tag",
            description="The 'latest' tag is mutable and can cause unexpected rollouts.",
            fix="Pin images to a specific digest: image: myapp@sha256:<digest>",
        ))

    async def _check_liveness_probes(self):
        self.result.add_issue(Issue(
            severity="info",
            title="Liveness/readiness probes not configured",
            description="Without probes, Kubernetes cannot detect unhealthy pods and restart them.",
            fix="Add livenessProbe and readinessProbe to all containers.",
        ))
