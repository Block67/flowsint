"""
Follow funds through time and summarize accounts.
"""

from collections import defaultdict
from typing import Dict, List, Literal, Optional, Tuple

from .models import AccountSummary, TraceResult, TxEdge


def trace_funds(
    edges: List[TxEdge],
    start: str,
    direction: Literal["downstream", "upstream"] = "downstream",
    max_hops: int = 4,
    since: Optional[int] = None,
) -> TraceResult:
    """Accounts reachable from `start` while respecting time order.

    downstream: where the money went (each next transfer happens after the
    money arrived). upstream: where it came from (each previous transfer
    happened before). Undated transfers are always followed.
    """
    downstream = direction == "downstream"
    adjacency: Dict[str, List[TxEdge]] = defaultdict(list)
    for e in edges:
        adjacency[e.source if downstream else e.target].append(e)

    # Earliest (downstream) / latest (upstream) time money was at each node
    reached: Dict[str, Tuple[int, Optional[int]]] = {start: (0, since)}
    labels: Dict[str, Optional[str]] = {}
    used_edges: Dict[str, None] = {}
    frontier = [start]

    for hop in range(1, max_hops + 1):
        next_frontier: List[str] = []
        for node in frontier:
            _, at = reached[node]
            for e in adjacency.get(node, []):
                if at is not None and e.epoch is not None:
                    if downstream and e.epoch < at:
                        continue
                    if not downstream and e.epoch > at:
                        continue
                other = e.target if downstream else e.source
                labels[node] = e.source_label if downstream else e.target_label
                labels[other] = e.target_label if downstream else e.source_label
                used_edges[e.id] = None
                time = e.epoch if e.epoch is not None else at
                if other not in reached:
                    reached[other] = (hop, time)
                    next_frontier.append(other)
                elif reached[other][0] == hop and time is not None:
                    # Same hop: keep the time that lets the trace go furthest
                    prev = reached[other][1]
                    if prev is None or (time < prev if downstream else time > prev):
                        reached[other] = (hop, time)
        frontier = next_frontier
        if not frontier:
            break

    return TraceResult(
        start_node_id=start,
        direction=direction,
        nodes={
            node: {"hops": hops, "first_seen": time, "label": labels.get(node)}
            for node, (hops, time) in reached.items()
        },
        edge_ids=list(used_edges),
    )


def summarize_accounts(edges: List[TxEdge]) -> List[AccountSummary]:
    """Per account and currency: volumes, counts and distinct counterparties,
    sorted by total volume."""
    stats: Dict[Tuple[str, str], Dict] = {}

    def entry(node: str, currency: str, label: Optional[str]) -> Dict:
        key = (node, currency)
        if key not in stats:
            stats[key] = {
                "label": label,
                "inflow": 0.0,
                "outflow": 0.0,
                "tx_in": 0,
                "tx_out": 0,
                "senders": set(),
                "receivers": set(),
                "first": None,
                "last": None,
            }
        return stats[key]

    for e in edges:
        currency = e.currency or ""
        out = entry(e.source, currency, e.source_label)
        out["outflow"] += e.amount
        out["tx_out"] += 1
        out["receivers"].add(e.target)
        inc = entry(e.target, currency, e.target_label)
        inc["inflow"] += e.amount
        inc["tx_in"] += 1
        inc["senders"].add(e.source)
        if e.epoch is not None:
            for s in (out, inc):
                s["first"] = e.epoch if s["first"] is None else min(s["first"], e.epoch)
                s["last"] = e.epoch if s["last"] is None else max(s["last"], e.epoch)

    summaries = [
        AccountSummary(
            node_id=node,
            label=s["label"],
            currency=currency or None,
            inflow=s["inflow"],
            outflow=s["outflow"],
            net=s["inflow"] - s["outflow"],
            tx_in=s["tx_in"],
            tx_out=s["tx_out"],
            senders=len(s["senders"]),
            receivers=len(s["receivers"]),
            first_seen=s["first"],
            last_seen=s["last"],
        )
        for (node, currency), s in stats.items()
    ]
    return sorted(summaries, key=lambda a: a.inflow + a.outflow, reverse=True)
