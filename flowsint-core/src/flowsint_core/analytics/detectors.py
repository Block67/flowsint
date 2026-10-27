"""
Pattern detectors over TRANSACTION edges. Pure functions: no graph access.

Time windows only consider dated edges; amounts are never summed across
currencies.
"""

from collections import Counter, defaultdict, deque
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

from .models import Alert, DetectionParams, TxEdge

HOUR = 3600

# Hard cap on DFS steps for cycle search so a dense graph can't hang a request.
MAX_CYCLE_SEARCH_STEPS = 200_000


def _label(edge: TxEdge, node_id: str) -> Optional[str]:
    return edge.source_label if node_id == edge.source else edge.target_label


def _ramp_score(value: float, minimum: float) -> float:
    """0.5 at the detection minimum, 1.0 at twice the minimum."""
    if minimum <= 0:
        return 1.0
    return round(0.5 + 0.5 * min(1.0, (value - minimum) / minimum), 2)


def detect_fan(edges: List[TxEdge], params: DetectionParams) -> List[Alert]:
    """Accounts sending to (fan-out) or receiving from (fan-in) many distinct
    counterparties within a sliding time window: splitting or collecting funds."""
    alerts: List[Alert] = []
    for direction in ("out", "in"):
        by_account: Dict[str, List[TxEdge]] = defaultdict(list)
        for e in edges:
            if e.epoch is None:
                continue
            by_account[e.source if direction == "out" else e.target].append(e)

        for account, account_edges in by_account.items():
            best = _best_fan_window(
                sorted(account_edges, key=lambda e: e.epoch),
                lambda e: e.target if direction == "out" else e.source,
                params.fan_window_hours * HOUR,
            )
            if best is None:
                continue
            window_edges, counterparties = best
            if len(counterparties) < params.fan_min_counterparties:
                continue
            label = _label(window_edges[0], account) or account
            verb = "sent to" if direction == "out" else "received from"
            alerts.append(
                Alert(
                    type=f"fan_{direction}",
                    title=f"{label} {verb} {len(counterparties)} accounts within {params.fan_window_hours:g}h",
                    score=_ramp_score(
                        len(counterparties), params.fan_min_counterparties
                    ),
                    node_ids=[account, *sorted(counterparties)],
                    edge_ids=[e.id for e in window_edges],
                    details={
                        "account": account,
                        "counterparties": len(counterparties),
                        "transactions": len(window_edges),
                        "start": window_edges[0].epoch,
                        "end": window_edges[-1].epoch,
                        "totals": _totals_by_currency(window_edges),
                    },
                )
            )
    return alerts


def _best_fan_window(
    edges: List[TxEdge], counterparty: Callable[[TxEdge], str], window: float
) -> Optional[Tuple[List[TxEdge], Set[str]]]:
    best: Optional[Tuple[List[TxEdge], Set[str]]] = None
    counts: Counter = Counter()
    start = 0
    for end, edge in enumerate(edges):
        counts[counterparty(edge)] += 1
        while edge.epoch - edges[start].epoch > window:
            old = counterparty(edges[start])
            counts[old] -= 1
            if counts[old] == 0:
                del counts[old]
            start += 1
        if best is None or len(counts) > len(best[1]):
            best = (edges[start : end + 1], set(counts))
    return best


def _totals_by_currency(edges: Iterable[TxEdge]) -> Dict[str, float]:
    totals: Dict[str, float] = defaultdict(float)
    for e in edges:
        totals[e.currency or ""] += e.amount
    return dict(totals)


def detect_pass_through(edges: List[TxEdge], params: DetectionParams) -> List[Alert]:
    """Accounts that send on most of what they receive shortly after receiving
    it (mule / layering behaviour). Compared per currency."""
    window = params.pass_through_window_hours * HOUR
    inflows: Dict[Tuple[str, str], List[TxEdge]] = defaultdict(list)
    outflows: Dict[Tuple[str, str], List[TxEdge]] = defaultdict(list)
    for e in edges:
        if e.epoch is None:
            continue
        inflows[(e.target, e.currency or "")].append(e)
        outflows[(e.source, e.currency or "")].append(e)

    alerts: List[Alert] = []
    for key, ins in inflows.items():
        outs = sorted(outflows.get(key, []), key=lambda e: e.epoch)
        if not outs:
            continue
        account, currency = key
        events, matched_out = _match_forwarded(
            sorted(ins, key=lambda e: e.epoch), outs, window, params
        )
        if len(events) < params.pass_through_min_events:
            continue
        # What makes a mule is that most of *all* the money it receives moves on
        # quickly; ordinary busy accounts forward some transfers by chance.
        total_received = sum(
            i.amount for i in ins if i.amount >= params.pass_through_min_amount
        )
        forwarded = sum(amount for _, amount in events)
        share = forwarded / total_received if total_received else 0.0
        if share < params.pass_through_min_share:
            continue

        label = _label(events[0][0], account) or account
        alerts.append(
            Alert(
                type="pass_through",
                title=f"{label} forwarded {share:.0%} of what it received within {params.pass_through_window_hours:g}h",
                score=round(min(1.0, share), 2),
                node_ids=[account]
                + sorted(
                    {i.source for i, _ in events}
                    | {o.target for o in matched_out.values()}
                ),
                edge_ids=[i.id for i, _ in events] + list(matched_out),
                details={
                    "account": account,
                    "currency": currency or None,
                    "events": len(events),
                    "incoming_transfers": len(ins),
                    "received": total_received,
                    "forwarded": forwarded,
                    "forwarded_share": round(share, 4),
                },
            )
        )
    return alerts


def _match_forwarded(
    ins: List[TxEdge], outs: List[TxEdge], window: float, params: DetectionParams
) -> Tuple[List[Tuple[TxEdge, float]], Dict[str, TxEdge]]:
    """FIFO-allocate each outflow to the oldest still-open inflows (received at
    most `window` before it), so one large outflow can't explain many inflows.
    An inflow counts as forwarded when enough of it was allocated."""
    allocated: Dict[str, float] = defaultdict(float)
    used_outs: Dict[str, List[TxEdge]] = defaultdict(list)
    pending: deque = deque()
    i = 0
    for out in outs:
        while i < len(ins) and ins[i].epoch <= out.epoch:
            if ins[i].amount > 0 and ins[i].amount >= params.pass_through_min_amount:
                pending.append(ins[i])
            i += 1
        while pending and out.epoch - pending[0].epoch > window:
            pending.popleft()
        remaining = out.amount
        while pending and remaining > 0:
            inflow = pending[0]
            give = min(remaining, inflow.amount - allocated[inflow.id])
            allocated[inflow.id] += give
            used_outs[inflow.id].append(out)
            remaining -= give
            if allocated[inflow.id] >= inflow.amount:
                pending.popleft()

    events: List[Tuple[TxEdge, float]] = []
    matched_out: Dict[str, TxEdge] = {}
    for inflow in ins:
        if allocated[inflow.id] >= params.pass_through_ratio * inflow.amount > 0:
            events.append((inflow, allocated[inflow.id]))
            matched_out.update({o.id: o for o in used_outs[inflow.id]})
    return events, matched_out


def detect_structuring(edges: List[TxEdge], params: DetectionParams) -> List[Alert]:
    """Several amounts just below a threshold from the same sender or to the
    same recipient within a window (splitting to stay under reporting limits)."""
    threshold = params.structuring_threshold
    if not threshold:
        return []
    low = threshold * (1 - params.structuring_margin)
    wanted_currency = (params.structuring_currency or "").upper() or None
    near = [
        e
        for e in edges
        if e.epoch is not None
        and low <= e.amount < threshold
        and (wanted_currency is None or (e.currency or "").upper() == wanted_currency)
    ]

    window = params.structuring_window_hours * HOUR
    alerts: List[Alert] = []
    for role in ("source", "target"):
        groups: Dict[Tuple[str, str], List[TxEdge]] = defaultdict(list)
        for e in near:
            groups[(getattr(e, role), e.currency or "")].append(e)
        for (account, currency), group in groups.items():
            group.sort(key=lambda e: e.epoch)
            best: List[TxEdge] = []
            start = 0
            for end in range(len(group)):
                while group[end].epoch - group[start].epoch > window:
                    start += 1
                if end - start + 1 > len(best):
                    best = group[start : end + 1]
            if len(best) < params.structuring_min_count:
                continue
            label = _label(best[0], account) or account
            verb = "sent" if role == "source" else "received"
            alerts.append(
                Alert(
                    type="structuring",
                    title=f"{label} {verb} {len(best)} amounts just under {threshold:,.0f} {currency}".rstrip(),
                    score=_ramp_score(len(best), params.structuring_min_count),
                    node_ids=[account]
                    + sorted(
                        {e.target if role == "source" else e.source for e in best}
                    ),
                    edge_ids=[e.id for e in best],
                    details={
                        "account": account,
                        "role": role,
                        "currency": currency or None,
                        "threshold": threshold,
                        "count": len(best),
                        "total": sum(e.amount for e in best),
                    },
                )
            )
    return alerts


def detect_cycles(edges: List[TxEdge], params: DetectionParams) -> List[Alert]:
    """Money that returns to an account through a chain of transfers, each one
    happening after the previous (undated edges fit anywhere)."""
    out_edges: Dict[str, List[TxEdge]] = defaultdict(list)
    for e in edges:
        if e.source != e.target:
            out_edges[e.source].append(e)

    window = params.cycle_window_hours * HOUR if params.cycle_window_hours else None
    seen: Set[frozenset] = set()
    cycles: List[List[TxEdge]] = []
    steps = 0

    def dfs(
        start: str,
        path: List[TxEdge],
        visited: Set[str],
        last: Optional[int],
        first: Optional[int],
    ):
        nonlocal steps
        node = path[-1].target
        for e in out_edges.get(node, []):
            steps += 1
            if steps > MAX_CYCLE_SEARCH_STEPS or len(cycles) >= params.max_cycles:
                return
            if last is not None and e.epoch is not None and e.epoch < last:
                continue
            new_first = first if first is not None else e.epoch
            if (
                window
                and e.epoch is not None
                and new_first is not None
                and e.epoch - new_first > window
            ):
                continue
            new_last = e.epoch if e.epoch is not None else last
            if e.target == start:
                if len(path) + 1 >= params.cycle_min_length:
                    key = frozenset(x.id for x in path + [e])
                    if key not in seen:
                        seen.add(key)
                        cycles.append(path + [e])
                continue
            if e.target in visited or len(path) + 1 >= params.cycle_max_length:
                continue
            visited.add(e.target)
            dfs(start, path + [e], visited, new_last, new_first)
            visited.discard(e.target)

    for first_edge in sorted(edges, key=lambda e: (e.epoch is None, e.epoch or 0)):
        if first_edge.source == first_edge.target:
            continue
        if steps > MAX_CYCLE_SEARCH_STEPS or len(cycles) >= params.max_cycles:
            break
        dfs(
            first_edge.source,
            [first_edge],
            {first_edge.source, first_edge.target},
            first_edge.epoch,
            first_edge.epoch,
        )

    alerts: List[Alert] = []
    for cycle in cycles:
        start = cycle[0].source
        label = cycle[0].source_label or start
        sent, returned = cycle[0].amount, cycle[-1].amount
        same_currency = cycle[0].currency == cycle[-1].currency
        return_ratio = returned / sent if sent and same_currency else None
        alerts.append(
            Alert(
                type="cycle",
                title=f"Funds from {label} came back after {len(cycle)} transfers",
                score=0.9 if return_ratio is not None and return_ratio >= 0.5 else 0.6,
                node_ids=[e.source for e in cycle],
                edge_ids=[e.id for e in cycle],
                details={
                    "account": start,
                    "length": len(cycle),
                    "sent": sent,
                    "returned": returned,
                    "currency": cycle[0].currency,
                    "return_ratio": return_ratio,
                    "search_truncated": steps > MAX_CYCLE_SEARCH_STEPS,
                },
            )
        )
    return alerts


DETECTORS = {
    "fan": detect_fan,
    "pass_through": detect_pass_through,
    "structuring": detect_structuring,
    "cycle": detect_cycles,
}


def run_detectors(
    edges: List[TxEdge],
    params: Optional[DetectionParams] = None,
    only: Optional[Iterable[str]] = None,
) -> List[Alert]:
    params = params or DetectionParams()
    names = list(only) if only else list(DETECTORS)
    alerts: List[Alert] = []
    for name in names:
        if name not in DETECTORS:
            raise ValueError(f"Unknown detector: {name}")
        alerts.extend(DETECTORS[name](edges, params))
    return sorted(alerts, key=lambda a: a.score, reverse=True)
