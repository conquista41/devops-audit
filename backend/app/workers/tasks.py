import asyncio
import logging
from datetime import datetime, timezone
from app.workers.celery_app import celery_app
from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


def run_async(coro):
    """Run async code inside a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def run_scan(self, scan_id: str, scan_type: str, target: str, config: dict):
    """Main scan orchestrator task."""
    return run_async(_run_scan_async(self, scan_id, scan_type, target, config))


async def _run_scan_async(task, scan_id: str, scan_type: str, target: str, config: dict):
    from sqlalchemy import select
    from sqlalchemy.orm.attributes import flag_modified
    from app.core.database import AsyncSessionLocal
    from app.models.models import Scan, ScanStatus
    from app.scanners.github_scanner import GitHubScanner
    from app.scanners.k8s_scanner import KubernetesScanner
    from app.scanners.container_scanner import ContainerScanner

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Scan).where(Scan.id == scan_id))
        scan = result.scalar_one_or_none()
        if not scan:
            return {"error": "Scan not found"}

        scan.status = ScanStatus.RUNNING
        scan.started_at = datetime.now(timezone.utc)
        await db.commit()

        try:
            if settings.DEMO_MODE:
                from app.scanners.demo_results import get_demo_results
                await asyncio.sleep(2)  # Simulate scan time
                results = get_demo_results(scan_type, target)
            else:
                scanner_map = {
                    "github": GitHubScanner,
                    "kubernetes": KubernetesScanner,
                    "container": ContainerScanner,
                }

                scanner_class = scanner_map.get(scan_type)
                if not scanner_class:
                    raise ValueError(f"Unknown scan type: {scan_type}")

                scanner = scanner_class(target=target, config=config)
                results = await scanner.run()

            logger.info(
                "[scan %s] results ready: score=%s issues=%d",
                scan_id, results.get("score"), len(results.get("issues", [])),
            )

            scan.status = ScanStatus.COMPLETED
            scan.results = results
            flag_modified(scan, "results")  # ensure SQLAlchemy marks JSON column dirty
            scan.score = results.get("score", 0)
            scan.issues_critical = results.get("summary", {}).get("critical", 0)
            scan.issues_warning = results.get("summary", {}).get("warning", 0)
            scan.issues_info = results.get("summary", {}).get("info", 0)
            scan.completed_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info(
                "[scan %s] committed: status=%s score=%s results_keys=%s",
                scan_id, scan.status, scan.score,
                list(scan.results.keys()) if scan.results else None,
            )

            if not settings.DEMO_MODE:
                generate_report.delay(scan_id)
            return {"scan_id": scan_id, "status": "completed", "score": scan.score}

        except Exception as exc:
            scan.status = ScanStatus.FAILED
            scan.error_message = str(exc)[:1000]
            scan.completed_at = datetime.now(timezone.utc)
            await db.commit()
            raise task.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2)
def generate_report(self, scan_id: str):
    """Generate PDF report after scan completes."""
    return run_async(_generate_report_async(scan_id))


async def _generate_report_async(scan_id: str):
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.models import Scan, Report
    from app.services.report_generator import generate_pdf_report
    from app.services.s3 import upload_report

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Scan).where(Scan.id == scan_id))
        scan = result.scalar_one_or_none()
        if not scan or not scan.results:
            return

        pdf_bytes = await generate_pdf_report(scan)
        s3_key, s3_url = await upload_report(scan_id, pdf_bytes)

        report = Report(scan_id=scan.id, s3_key=s3_key, s3_url=s3_url)
        db.add(report)
        await db.commit()
        return {"report_url": s3_url}
