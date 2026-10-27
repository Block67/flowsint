import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from flowsint_core.core.enricher_base import Enricher
from flowsint_core.core.logger import Logger
from flowsint_enrichers.crypto._common import (
    ETHERSCAN_V2_URL,
    EVM_CHAIN_PARAM,
    EVM_CHAINS,
    etherscan_get,
    to_units,
    write_transactions,
)
from flowsint_enrichers.registry import flowsint_enricher
from flowsint_types.transaction import Transaction
from flowsint_types.wallet import CryptoWallet

load_dotenv()


def wei_to_eth(wei_str):
    return to_units(wei_str, 18)


@flowsint_enricher
class CryptoWalletAddressToTransactions(Enricher):
    """[ETHERSCAN] Resolve native-coin transactions for an EVM wallet (ETH, BSC, Polygon...)."""

    # Define types as class attributes - base class handles schema generation automatically
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
    def required_params(cls) -> bool:
        return True

    @classmethod
    def icon(cls) -> str | None:
        return "cryptowallet"

    @classmethod
    def get_params_schema(cls) -> List[Dict[str, Any]]:
        """Declare required parameters for this enricher"""
        return [
            {
                "name": "ETHERSCAN_API_KEY",
                "type": "vaultSecret",
                "description": "The Etherscan API key to use for the transaction lookup.",
                "required": True,
            },
            EVM_CHAIN_PARAM,
            {
                "name": "MAX_TRANSACTIONS",
                "type": "number",
                "description": "Most recent transactions to fetch per wallet (max 10000).",
                "required": False,
                "default": "100",
            },
            {
                "name": "ETHERSCAN_API_URL",
                "type": "url",
                "description": "The Etherscan API URL to use for the transaction lookup.",
                "required": False,
                "default": ETHERSCAN_V2_URL,
            },
        ]

    @classmethod
    def name(cls) -> str:
        return "cryptowallet_to_transactions"

    @classmethod
    def category(cls) -> str:
        return "CryptoWallet"

    @classmethod
    def key(cls) -> str:
        return "address"

    async def scan(self, data: List[InputType]) -> List[OutputType]:
        results: List[OutputType] = []
        params = self.get_params()
        api_key = self.get_secret("ETHERSCAN_API_KEY", os.getenv("ETHERSCAN_API_KEY"))
        api_url = params.get("ETHERSCAN_API_URL") or ETHERSCAN_V2_URL
        chain_id = str(params.get("CHAIN_ID") or "1")
        limit = min(int(params.get("MAX_TRANSACTIONS") or 100), 10000)
        for d in data:
            if d.chain in ("bitcoin", "tron"):
                Logger.warn(
                    self.sketch_id,
                    {"message": f"Skipping {d.address}: not an EVM address."},
                )
                continue
            try:
                results.extend(
                    self._get_transactions(d.address, api_key, api_url, chain_id, limit)
                )
            except Exception as e:
                Logger.error(
                    self.sketch_id,
                    {"message": f"Error resolving transactions for {d.address}: {e}"},
                )
        return results

    def _get_transactions(
        self, address: str, api_key: str, api_url: str, chain_id: str, limit: int
    ) -> List[Transaction]:
        chain, currency = EVM_CHAINS.get(chain_id, (f"evm-{chain_id}", None))
        rows = etherscan_get(
            api_url,
            {
                "chainid": chain_id,
                "module": "account",
                "action": "txlist",
                "address": address,
                "startblock": 0,
                "endblock": 99999999,
                "page": 1,
                "offset": limit,
                "sort": "desc",
                "apikey": api_key,
            },
        )
        transactions = []
        for tx in rows:
            # Contract creation transactions have no "to"
            target_address = tx["to"] or tx["contractAddress"] or address
            transactions.append(
                Transaction(
                    transaction_id=tx["hash"],
                    source=CryptoWallet(address=tx["from"], chain=chain),
                    target=CryptoWallet(address=target_address, chain=chain),
                    amount=wei_to_eth(tx["value"]),
                    currency=currency,
                    timestamp=int(tx["timeStamp"]),
                    channel="crypto",
                    status="failed" if tx.get("isError") == "1" else "success",
                    fees=wei_to_eth(int(tx["gasUsed"]) * int(tx["gasPrice"])),
                    chain=chain,
                    block_number=int(tx["blockNumber"]),
                    contract_address=tx["contractAddress"] or None,
                    function_name=tx.get("functionName") or None,
                )
            )
        return transactions

    def postprocess(
        self, results: List[OutputType], original_input: List[InputType]
    ) -> List[OutputType]:
        if self._graph_service:
            write_transactions(self, results)
        return results


# Make types available at module level for easy access
InputType = CryptoWalletAddressToTransactions.InputType
OutputType = CryptoWalletAddressToTransactions.OutputType
