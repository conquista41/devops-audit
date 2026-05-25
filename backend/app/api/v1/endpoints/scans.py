from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db
from app.models.models import User, Scan, ScanType, ScanStatus
from app.api.v1.endpoints.users import get_current_user
from pydantic import BaseModel
import uuid

router = APIRouter(prefix="/scans", tags=["scans"])


class ScanCreateRequest(BaseModel):
    scan_type: ScanType
    target: str
    config: dict = {}


class ScanResponse(BaseModel):
    id: uuid.UUID
    scan_type: str
    status: str
    target: str
    score: int | None
    issues_critical: int
    issues_warning: int
    issues_info: int
    results: dict | None = None
    celery_task_id: str | None
    error_message: str | None
    created_at: str

    model_config = {"from_attributes": True}


@router.post("/", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
async def create_scan(
    body: ScanCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.scans_used_this_month >= current_user.scan_limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Monthly scan limit reached ({current_user.scan_limit}). Upgrade to Pro.",
        )

    scan = Scan(
        user_id=current_user.id,
        scan_type=body.scan_type,
        target=body.target,
        config=body.config,
        status=ScanStatus.PENDING,
    )
    db.add(scan)
    await db.flush()

    # Dispatch Celery task
    from app.workers.tasks import run_scan
    task = run_scan.delay(str(scan.id), body.scan_type.value, body.target, body.config)
    scan.celery_task_id = task.id

    current_user.scans_used_this_month += 1

    return ScanResponse(
        id=scan.id,
        scan_type=scan.scan_type.value,
        status=scan.status.value,
        target=scan.target,
        score=scan.score,
        issues_critical=scan.issues_critical,
        issues_warning=scan.issues_warning,
        issues_info=scan.issues_info,
        results=scan.results,
        celery_task_id=scan.celery_task_id,
        error_message=scan.error_message,
        created_at=scan.created_at.isoformat(),
    )


@router.get("/", response_model=list[ScanResponse])
async def list_scans(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 20,
    offset: int = 0,
):
    result = await db.execute(
        select(Scan)
        .where(Scan.user_id == current_user.id)
        .order_by(desc(Scan.created_at))
        .limit(limit)
        .offset(offset)
    )
    scans = result.scalars().all()
    return [
        ScanResponse(
            id=s.id,
            scan_type=s.scan_type.value,
            status=s.status.value,
            target=s.target,
            score=s.score,
            issues_critical=s.issues_critical,
            issues_warning=s.issues_warning,
            issues_info=s.issues_info,
            celery_task_id=s.celery_task_id,
            error_message=s.error_message,
            created_at=s.created_at.isoformat(),
        )
        for s in scans
    ]


@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan(
    scan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Scan).where(Scan.id == scan_id, Scan.user_id == current_user.id)
    )
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    return ScanResponse(
        id=scan.id,
        scan_type=scan.scan_type.value,
        status=scan.status.value,
        target=scan.target,
        score=scan.score,
        issues_critical=scan.issues_critical,
        issues_warning=scan.issues_warning,
        issues_info=scan.issues_info,
        results=scan.results,
        celery_task_id=scan.celery_task_id,
        error_message=scan.error_message,
        created_at=scan.created_at.isoformat(),
    )
