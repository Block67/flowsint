"""
Shared helpers for crypto enrichers (private module: not an enricher).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

import requests

from flowsint_core.core.enricher_base import Enricher
from flowsint_types.transaction import Transaction

ETHERSCAN_V2_URL = "https://api.etherscan.io/v2/api"

# Etherscan v2 chain id -> (chain name stored on wallets, native currency)
EVM_CHAINS: Dict[str, tuple] = {
    "1": ("ethereum", "ETH"),
    "56": ("bsc", "BNB"),
    "137": ("polygon", "POL"),
    "42161": ("arbitrum", "ETH"),
    "10": ("optimism", "ETH"),
    "8453": ("base", "ETH"),
    "43114": ("avalanche", "AVAX"),
}

EVM_CHAIN_PARAM = {
    "name": "CHAIN_ID",
    "type": "select",
    "description": "EVM chain to query (Etherscan v2 chain id).",
    "required": False,
    "default": "1",
    "options": [
        {"label": f"{name.capitalize()} ({currency})", "value": chain_id}
        for chain_id, (name, currency) in EVM_CHAINS.items()
    ],
}

REQUEST_TIMEOUT = 30


def etherscan_get(api_url: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Call Etherscan v2 and return `result`. "No transactions found" is an
    empty list, not an error."""
    response = requests.get(api_url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    data = response.json()
    if data.get("status") != "1":
        message = str(data.get("message", ""))
        if message.lower().startswith("no ") and data.get("result") in ([], None):
            return []
        raise ValueError(f"Etherscan error: {message} - {data.get('result')}")
    return data.get("result") or []


def to_units(raw: Any, decimals: int) -> float:
    """Integer base units (wei, sun, satoshi...) to a decimal amount."""
    return int(raw) / 10**decimals


def write_transactions(enricher: Enricher, transactions: List[Transaction]) -> None:
    """Create both account nodes and one TRANSACTION edge per transaction."""
    for tx in transactions:
        enricher.create_node(tx.source)
        enricher.create_node(tx.target)
        enricher.create_relationship(
            tx.source,
            tx.target,
            "TRANSACTION",
            properties=tx.edge_properties(),
            edge_key=tx.transaction_id,
        )
        when = tx.timestamp.strftime("%Y-%m-%d %H:%M:%S") if tx.timestamp else "pending"
        enricher.log_graph_message(
            f"Transaction on {when}: {tx.source.nodeLabel} -> {tx.target.nodeLabel} ({tx.caption})"
        )


def epoch_ms_to_datetime(value: Any) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
