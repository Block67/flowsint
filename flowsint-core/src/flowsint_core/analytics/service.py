from typing import Iterable, List, Literal, Optional

from flowsint_core.core.graph import GraphService

from .detectors import run_detectors
from .flows import summarize_accounts, trace_funds
from .loader import load_transactions
from .models import AccountSummary, Alert, DetectionParams, TraceResult


class TransactionAnalyticsService:
    """Money-flow analysis over a sketch's TRANSACTION edges."""

    def __init__(self, graph_service: GraphService):
        self._graph_service = graph_service

    def detect(
        self,
        params: Optional[DetectionParams] = None,
        only: Optional[Iterable[str]] = None,
    ) -> List[Alert]:
        return run_detectors(load_transactions(self._graph_service), params, only)

    def trace(
        self,
        start_node_id: str,
        direction: Literal["downstream", "upstream"] = "downstream",
        max_hops: int = 4,
        since: Optional[int] = None,
    ) -> TraceResult:
        return trace_funds(
            load_transactions(self._graph_service),
            start_node_id,
            direction=direction,
            max_hops=max_hops,
            since=since,
        )

    def summary(self, limit: int = 50) -> List[AccountSummary]:
        return summarize_accounts(load_transactions(self._graph_service))[:limit]
