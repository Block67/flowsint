from collections import defaultdict
from typing import Any, Dict, List, Optional

import requests

from flowsint_core.core.enricher_base import Enricher
from flowsint_core.core.logger import Logger
from flowsint_enrichers.crypto._common import (
    REQUEST_TIMEOUT,
    to_units,
    write_transactions,
)
from flowsint_enrichers.registry import flowsint_enricher
from flowsint_types.transaction import Transaction
from flowsint_types.wallet import CryptoWallet

MEMPOOL_API_URL = "https://mempool.space/api"


def utxo_transfers(tx: Dict[str, Any], address: str) -> List[Transaction]:
    """Turn one Bitcoin transaction into address-to-address transfers seen from
    `address`.

    Bitcoin moves coins from a set of inputs to a set of outputs, with no
    explicit "who paid whom". When `address` spends, it is credited with its
    share of the inputs on every output that doesn't go back to an input
    address (change). When it receives, each input address is credited with
    its share of what `address` received.
    """
    if any(vin.get("is_coinbase") for vin in tx.get("vin", [])):
        return []

    inputs: Dict[str, int] = defaultdict(int)
    for vin in tx.get("vin", []):
        prevout = vin.get("prevout") or {}
        if prevout.get("scriptpubkey_address"):
            inputs[prevout["scriptpubkey_address"]] += int(prevout.get("value", 0))
    outputs: Dict[str, int] = defaultdict(int)
    for vout in tx.get("vout", []):
        if vout.get("scriptpubkey_address"):
            outputs[vout["scriptpubkey_address"]] += int(vout.get("value", 0))

    total_in = sum(inputs.values())
    if not total_in:
        return []

    pairs: List[tuple] = []  # (from, to, satoshis)
    if address in inputs:
        share = inputs[address] / total_in
        for out_address, value in outputs.items():
            if out_address not in inputs:
                pairs.append((address, out_address, value * share))
    elif address in outputs:
        received = outputs[address]
        for in_address, value in inputs.items():
            pairs.append((in_address, address, received * value / total_in))

    status = tx.get("status") or {}
    confirmed = bool(status.get("confirmed"))
    return [
        Transaction(
            transaction_id=f"{tx['txid']}:{src}:{dst}",
            source=CryptoWallet(address=src, chain="bitcoin"),
            target=CryptoWallet(address=dst, chain="bitcoin"),
            amount=to_units(round(sats), 8),
            currency="BTC",
            timestamp=status.get("block_time") if confirmed else None,
            channel="crypto",
            status="success" if confirmed else "pending",
            chain="bitcoin",
            tx_hash=tx["txid"],
            block_number=status.get("block_height"),
        )
        for src, dst, sats in pairs
        if sats > 0
    ]


@flowsint_enricher
class CryptoWalletToBtcTransactions(Enricher):
    """[MEMPOOL] Resolve Bitcoin transfers for a BTC address (no API key needed)."""

    InputType = CryptoWallet
    OutputType = Transaction

    def __init__(
        self,
        sketch_id: Optional[str] = None,
        scan_id: Optional[str] = None,
        vault=None,
        params: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            sketch_id=sketch_id,
            scan_id=scan_id,
            params_schema=self.get_params_schema(),
            vault=vault,
            params=params,
        )

    @classmethod
    def icon(cls) -> str | None:
        return "cryptowallet"

    @classmethod
    def get_params_schema(cls) -> List[Dict[str, Any]]:
        return [
            {
                "name": "MAX_PAGES",
                "type": "number",
                "description": "Pages of 25 confirmed transactions to fetch per address.",
                "required": False,
                "default": "2",
            },
            {
                "name": "MEMPOOL_API_URL",
                "type": "url",
                "description": "Esplora-compatible API (mempool.space, blockstream.info, self-hosted).",
                "required": False,
                "default": MEMPOOL_API_URL,
            },
        ]

    @classmethod
    def name(cls) -> str:
        return "cryptowallet_to_btc_transactions"

    @classmethod
    def category(cls) -> str:
        return "CryptoWallet"

    @classmethod
    def key(cls) -> str:
        return "address"

    async def scan(self, data: List[InputType]) -> List[OutputType]:
        results: List[OutputType] = []
        params = self.get_params()
        api_url = (params.get("MEMPOOL_API_URL") or MEMPOOL_API_URL).rstrip("/")
        max_pages = max(1, int(params.get("MAX_PAGES") or 2))
        for d in data:
            if d.chain != "bitcoin":
                Logger.warn(
                    self.sketch_id,
                    {"message": f"Skipping {d.address}: not a Bitcoin address."},
                )
                continue
            try:
                for tx in self._fetch_txs(api_url, d.address, max_pages):
                    results.extend(utxo_transfers(tx, d.address))
            except Exception as e:
                Logger.error(
                    self.sketch_id,
                    {
                        "message": f"Error resolving BTC transactions for {d.address}: {e}"
                    },
                )
        return results

    def _fetch_txs(
        self, api_url: str, address: str, max_pages: int
    ) -> List[Dict[str, Any]]:
        """First page has unconfirmed + 25 confirmed txs, then page by last txid."""
        txs: List[Dict[str, Any]] = []
        url = f"{api_url}/address/{address}/txs"
        for _ in range(max_pages):
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            page = response.json()
            txs.extend(page)
            confirmed = [t for t in page if (t.get("status") or {}).get("confirmed")]
            if len(confirmed) < 25:
                break
            url = f"{api_url}/address/{address}/txs/chain/{confirmed[-1]['txid']}"
        return txs

    def postprocess(
        self, results: List[OutputType], original_input: List[InputType]
    ) -> List[OutputType]:
        if self._graph_service:
            write_transactions(self, results)
        return results


InputType = CryptoWalletToBtcTransactions.InputType
OutputType = CryptoWalletToBtcTransactions.OutputType
