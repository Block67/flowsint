from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class TxEdge:
    """A TRANSACTION relationship as loaded from the graph."""

    id: str
    source: str
    target: str
    amount: float
    currency: Optional[str] = None
    amount_usd: Optional[float] = None
    epoch: Optional[int] = None
    transaction_id: Optional[str] = None
    source_label: Optional[str] = None
    target_label: Optional[str] = None


@dataclass
class Alert:
    """A suspicious pattern, pointing at the graph nodes/edges involved."""

    type: str
    title: str
    score: float  # 0..1, how strongly the pattern matches
    node_ids: List[str]
    edge_ids: List[str]
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectionParams:
    # Fan-out / fan-in: many distinct counterparties in a short window
    fan_window_hours: float = 24
    fan_min_counterparties: int = 5

    # Pass-through: money received then sent on almost entirely, quickly
    pass_through_window_hours: float = 48
    pass_through_ratio: float = 0.8
    pass_through_min_amount: float = 0
    pass_through_min_events: int = 2
    # Share of everything the account received that was forwarded
    pass_through_min_share: float = 0.5

    # Structuring: repeated amounts just below a reporting threshold.
    # Disabled unless a threshold is given (it depends on currency and country).
    structuring_threshold: Optional[float] = None
    structuring_currency: Optional[str] = None
    structuring_margin: float = 0.1
    structuring_window_hours: float = 72
    structuring_min_count: int = 3

    # Cycles: money coming back to where it started, in time order
    cycle_min_length: int = 2
    cycle_max_length: int = 6
    cycle_window_hours: Optional[float] = None
    max_cycles: int = 100


@dataclass
class AccountSummary:
    node_id: str
    label: Optional[str]
    currency: Optional[str]
    inflow: float
    outflow: float
    tx_in: int
    tx_out: int
    senders: int
    receivers: int
    first_seen: Optional[int]
    last_seen: Optional[int]
    net: float  # inflow - outflow


@dataclass
class TraceResult:
    start_node_id: str
    direction: str
    # node id -> {"hops": int, "first_seen": epoch or None, "label": str}
    nodes: Dict[str, Dict[str, Any]]
    edge_ids: List[str]
