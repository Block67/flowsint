from typing import Any, Dict, List, Optional

import requests

from flowsint_core.core.enricher_base import Enricher
from flowsint_core.core.logger import Logger
from flowsint_enrichers.crypto._common import (
    REQUEST_TIMEOUT,
    epoch_ms_to_datetime,
    to_units,
    write_transactions,
)
from flowsint_enrichers.registry import flowsint_enricher
from flowsint_types.transaction import Transaction
from flowsint_types.wallet import CryptoWallet

TRONGRID_API_URL = "https://api.trongrid.io"
USDT_TRC20 = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
PAGE_SIZE = 200


@flowsint_enricher
class CryptoWalletToTrc20Transfers(Enricher):
    """[TRONGRID] Resolve TRC-20 token transfers (USDT by default) for a TRON address."""

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
                "name": "TRONGRID_API_KEY",
                "type": "vaultSecret",
                "description": "Optional TronGrid API key (higher rate limits).",
                "required": False,
            },
            {
                "name": "TOKEN_CONTRACT",
                "type": "string",
                "description": "Token contract to follow (default USDT). Empty = all tokens, including spam/dust tokens.",
                "required": False,
                "default": USDT_TRC20,
            },
            {
                "name": "MAX_TRANSACTIONS",
                "type": "number",
                "description": "Most recent transfers to fetch per address.",
                "required": False,
                "default": "200",
            },
            {
                "name": "TRONGRID_API_URL",
                "type": "url",
                "description": "TronGrid API URL.",
                "required": False,
                "default": TRONGRID_API_URL,
            },
        ]

    @classmethod
    def name(cls) -> str:
        return "cryptowallet_to_trc20_transfers"

    @classmethod
    def category(cls) -> str:
        return "CryptoWallet"

    @classmethod
    def key(cls) -> str:
        return "address"

    async def scan(self, data: List[InputType]) -> List[OutputType]:
        results: List[OutputType] = []
        params = self.get_params()
        api_url = (params.get("TRONGRID_API_URL") or TRONGRID_API_URL).rstrip("/")
        contract = params.get("TOKEN_CONTRACT", USDT_TRC20)
        contract = (contract or "").strip() or None
        limit = max(1, int(params.get("MAX_TRANSACTIONS") or 200))
        api_key = self.get_secret("TRONGRID_API_KEY")
        headers = {"TRON-PRO-API-KEY": api_key} if api_key else {}
        for d in data:
            if d.chain != "tron":
                Logger.warn(
                    self.sketch_id,
                    {"message": f"Skipping {d.address}: not a TRON address."},
                )
                continue
            try:
                rows = self._fetch(api_url, d.address, contract, limit, headers)
                results.extend(self._to_transaction(row) for row in rows)
            except Exception as e:
                Logger.error(
                    self.sketch_id,
                    {
                        "message": f"Error resolving TRC-20 transfers for {d.address}: {e}"
                    },
                )
        return results

    def _fetch(
        self,
        api_url: str,
        address: str,
        contract: Optional[str],
        limit: int,
        headers: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        url: Optional[str] = f"{api_url}/v1/accounts/{address}/transactions/trc20"
        query: Optional[Dict[str, Any]] = {
            "limit": min(PAGE_SIZE, limit),
            "only_confirmed": "true",
        }
        if contract:
            query["contract_address"] = contract
        rows: List[Dict[str, Any]] = []
        while url and len(rows) < limit:
            response = requests.get(
                url, params=query, headers=headers, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            body = response.json()
            if not body.get("success", True):
                raise ValueError(body.get("error") or "TronGrid error")
            rows.extend(body.get("data") or [])
            # The "next" link already carries every query parameter
            url = ((body.get("meta") or {}).get("links") or {}).get("next")
            query = None
        return rows[:limit]

    @staticmethod
    def _to_transaction(row: Dict[str, Any]) -> Transaction:
        token = row.get("token_info") or {}
        return Transaction(
            # One transaction can carry several transfers
            transaction_id=f"{row['transaction_id']}:{row['from']}:{row['to']}:{row['value']}",
            source=CryptoWallet(address=row["from"], chain="tron"),
            target=CryptoWallet(address=row["to"], chain="tron"),
            amount=to_units(row["value"], int(token.get("decimals") or 0)),
            currency=token.get("symbol"),
            timestamp=epoch_ms_to_datetime(row["block_timestamp"]),
            channel="crypto",
            chain="tron",
            tx_hash=row["transaction_id"],
            token_contract=token.get("address"),
        )

    def postprocess(
        self, results: List[OutputType], original_input: List[InputType]
    ) -> List[OutputType]:
        if self._graph_service:
            write_transactions(self, results)
        return results


InputType = CryptoWalletToTrc20Transfers.InputType
OutputType = CryptoWalletToTrc20Transfers.OutputType
