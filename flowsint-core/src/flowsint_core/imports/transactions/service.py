"""
Analyze, preview and import transaction statements into a sketch.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from flowsint_core.core.graph import GraphService
from flowsint_types import Transaction

from .mapping import TransactionMapping
from .parser import ParseOutcome, RowError, cell_str, parse_transactions
from .suggest import suggest_columns, suggest_mode
from .table_reader import read_table

SAMPLE_ROWS = 20
MAX_REPORTED_ERRORS = 50


@dataclass
class TableAnalysis:
    headers: List[str]
    sample_rows: List[Dict[str, Optional[str]]]
    total_rows: int
    suggested_columns: Dict[str, Optional[str]]
    suggested_mode: str


@dataclass
class TransactionPreview:
    total_rows: int
    valid_rows: int
    errors: List[RowError]
    sample: List[Dict[str, Any]]


@dataclass
class TransactionImportResult:
    status: str
    transactions_imported: int
    accounts_imported: int
    rows_failed: int
    errors: List[RowError] = field(default_factory=list)


def _transaction_summary(tx: Transaction) -> Dict[str, Any]:
    return {
        "transaction_id": tx.transaction_id,
        "source": tx.source.nodeLabel,
        "source_type": tx.source.__class__.__name__,
        "target": tx.target.nodeLabel,
        "target_type": tx.target.__class__.__name__,
        "amount": tx.amount,
        "currency": tx.currency,
        "timestamp": tx.timestamp.isoformat() if tx.timestamp else None,
        "description": tx.description,
    }


class TransactionImportService:
    def __init__(self, graph_service: Optional[GraphService] = None):
        self._graph_service = graph_service

    def analyze(self, file_bytes: bytes, filename: str) -> TableAnalysis:
        table = read_table(file_bytes, filename)
        suggested = suggest_columns(table.headers)
        return TableAnalysis(
            headers=table.headers,
            sample_rows=[
                {k: cell_str(v) for k, v in row.items()}
                for row in table.rows[:SAMPLE_ROWS]
            ],
            total_rows=len(table.rows),
            suggested_columns=suggested,
            suggested_mode=suggest_mode(suggested),
        )

    def parse(
        self, file_bytes: bytes, filename: str, mapping: TransactionMapping
    ) -> ParseOutcome:
        return parse_transactions(read_table(file_bytes, filename), mapping)

    def preview(
        self, file_bytes: bytes, filename: str, mapping: TransactionMapping
    ) -> TransactionPreview:
        outcome = self.parse(file_bytes, filename, mapping)
        return TransactionPreview(
            total_rows=len(outcome.transactions)
            + len(outcome.errors)
            + outcome.skipped_empty,
            valid_rows=len(outcome.transactions),
            errors=outcome.errors[:MAX_REPORTED_ERRORS],
            sample=[
                _transaction_summary(tx) for tx in outcome.transactions[:SAMPLE_ROWS]
            ],
        )

    def execute(
        self, file_bytes: bytes, filename: str, mapping: TransactionMapping
    ) -> TransactionImportResult:
        if self._graph_service is None:
            raise RuntimeError("A graph service is required to import transactions")
        outcome = self.parse(file_bytes, filename, mapping)

        accounts_written = set()
        for tx in outcome.transactions:
            for account in (tx.source, tx.target):
                key = (account.__class__.__name__, account.nodeLabel)
                if key not in accounts_written:
                    self._graph_service.create_node_from_flowsint_type(account)
                    accounts_written.add(key)
            self._graph_service.create_relationship(
                tx.source,
                tx.target,
                "TRANSACTION",
                properties=tx.edge_properties(),
                edge_key=tx.transaction_id,
            )
        self._graph_service.flush()

        return TransactionImportResult(
            status="completed" if not outcome.errors else "completed_with_errors",
            transactions_imported=len(outcome.transactions),
            accounts_imported=len(accounts_written),
            rows_failed=len(outcome.errors),
            errors=outcome.errors[:MAX_REPORTED_ERRORS],
        )
