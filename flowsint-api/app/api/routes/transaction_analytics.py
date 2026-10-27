from typing import List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from flowsint_core.analytics import (
    DETECTORS,
    AccountSummary,
    Alert,
    DetectionParams,
    TraceResult,
    TransactionAnalyticsService,
)
from flowsint_core.core.graph import create_graph_service
from flowsint_core.core.models import Profile
from flowsint_core.core.postgre_db import get_db
from flowsint_core.core.services import (
    NotFoundError,
    PermissionDeniedError,
    create_sketch_service,
)

router = APIRouter()


class AlertsRequest(BaseModel):
    detectors: Optional[List[str]] = Field(
        None, description=f"Subset of: {', '.join(DETECTORS)}. All when empty."
    )
    params: DetectionParams = Field(default_factory=DetectionParams)


class TraceRequest(BaseModel):
    node_id: str
    direction: Literal["downstream", "upstream"] = "downstream"
    max_hops: int = Field(4, ge=1, le=10)
    since: Optional[int] = Field(None, description="Unix epoch to start from")


def _analytics_service(
    db: Session, sketch_id: str, user_id: UUID
) -> TransactionAnalyticsService:
    try:
        create_sketch_service(db).get_by_id(UUID(sketch_id), user_id)
    except (NotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Sketch not found")
    except PermissionDeniedError:
        raise HTTPException(status_code=403, detail="Forbidden")
    return TransactionAnalyticsService(
        create_graph_service(sketch_id=sketch_id, enable_batching=False)
    )


@router.post("/{sketch_id}/transactions/alerts", response_model=List[Alert])
def detect_transaction_patterns(
    sketch_id: str,
    payload: AlertsRequest,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_user),
):
    """Run suspicious-pattern detectors over the sketch's transactions."""
    service = _analytics_service(db, sketch_id, current_user.id)
    try:
        return service.detect(payload.params, payload.detectors)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{sketch_id}/transactions/trace", response_model=TraceResult)
def trace_transaction_funds(
    sketch_id: str,
    payload: TraceRequest,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_user),
):
    """Follow funds from (or back to) an account, in time order."""
    service = _analytics_service(db, sketch_id, current_user.id)
    return service.trace(
        payload.node_id,
        direction=payload.direction,
        max_hops=payload.max_hops,
        since=payload.since,
    )


@router.get("/{sketch_id}/transactions/accounts", response_model=List[AccountSummary])
def summarize_transaction_accounts(
    sketch_id: str,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_user),
):
    """Per-account volumes and counterparties, by total volume."""
    service = _analytics_service(db, sketch_id, current_user.id)
    return service.summary(limit=max(1, min(limit, 1000)))
