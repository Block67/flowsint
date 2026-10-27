"""
Import of transaction statements (CSV / XLSX) as TRANSACTION edges.
"""

from .mapping import AccountSide, TransactionMapping
from .parser import ParseOutcome, RowError, parse_amount, parse_date, parse_transactions
from .service import (
    TableAnalysis,
    TransactionImportResult,
    TransactionImportService,
    TransactionPreview,
)
from .suggest import suggest_columns, suggest_mode
from .table_reader import ALLOWED_TABLE_EXTENSIONS, TableData, read_table

__all__ = [
    "ALLOWED_TABLE_EXTENSIONS",
    "AccountSide",
    "ParseOutcome",
    "RowError",
    "TableAnalysis",
    "TableData",
    "TransactionImportResult",
    "TransactionImportService",
    "TransactionMapping",
    "TransactionPreview",
    "parse_amount",
    "parse_date",
    "parse_transactions",
    "read_table",
    "suggest_columns",
    "suggest_mode",
]
