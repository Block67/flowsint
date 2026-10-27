from typing import List

from flowsint_core.core.graph import GraphService

from .models import TxEdge

TRANSACTIONS_QUERY = """
MATCH (a)-[r:TRANSACTION]->(b)
WHERE r.sketch_id = $sketch_id
  AND r.deleted_at IS NULL
  AND a.deleted_at IS NULL
  AND b.deleted_at IS NULL
RETURN elementId(r) AS id,
       elementId(a) AS source,
       elementId(b) AS target,
       a.nodeLabel AS source_label,
       b.nodeLabel AS target_label,
       r.amount AS amount,
       r.currency AS currency,
       r.amount_usd AS amount_usd,
       r.timestamp_epoch AS epoch,
       r.transaction_id AS transaction_id
"""


def load_transactions(graph_service: GraphService) -> List[TxEdge]:
    """All TRANSACTION edges of the graph service's sketch."""
    records = graph_service.query(
        TRANSACTIONS_QUERY, {"sketch_id": graph_service.sketch_id}
    )
    edges: List[TxEdge] = []
    for r in records or []:
        if r.get("amount") is None:
            continue
        edges.append(
            TxEdge(
                id=str(r["id"]),
                source=str(r["source"]),
                target=str(r["target"]),
                amount=float(r["amount"]),
                currency=r.get("currency"),
                amount_usd=r.get("amount_usd"),
                epoch=int(r["epoch"]) if r.get("epoch") is not None else None,
                transaction_id=r.get("transaction_id"),
                source_label=r.get("source_label"),
                target_label=r.get("target_label"),
            )
        )
    return edges
