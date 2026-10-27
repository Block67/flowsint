"""
Money-flow analytics over TRANSACTION edges: pattern detection, fund tracing
and account summaries.
"""

from .detectors import (
    DETECTORS,
    detect_cycles,
    detect_fan,
    detect_pass_through,
    detect_structuring,
    run_detectors,
)
from .flows import summarize_accounts, trace_funds
from .loader import load_transactions
from .models import AccountSummary, Alert, DetectionParams, TraceResult, TxEdge
from .service import TransactionAnalyticsService

__all__ = [
    "DETECTORS",
    "AccountSummary",
    "Alert",
    "DetectionParams",
    "TraceResult",
    "TransactionAnalyticsService",
    "TxEdge",
    "detect_cycles",
    "detect_fan",
    "detect_pass_through",
    "detect_structuring",
    "load_transactions",
    "run_detectors",
    "summarize_accounts",
    "trace_funds",
]
