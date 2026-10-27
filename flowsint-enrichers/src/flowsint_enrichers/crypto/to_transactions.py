import os
from typing import Any, Dict, List, Optional

import requests
import requests.exceptions
from dotenv import load_dotenv

from flowsint_core.core.enricher_base import Enricher
from flowsint_core.core.logger import Logger
from flowsint_enrichers.registry import flowsint_enricher
from flowsint_types.transaction import Transaction
from flowsint_types.wallet import CryptoWallet

load_dotenv()


def wei_to_eth(wei_str):
    return int(wei_str) / 10**18


@flowsint_enricher
class CryptoWalletAddressToTransactions(Enricher):
    """[ETHERSCAN] Resolve transactions for a wallet address (ETH)."""

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
            {
                "name": "ETHERSCAN_API_URL",
                "type": "url",
                "description": "The Etherscan API URL to use for the transaction lookup.",
                "required": False,
                "default": "https://api.etherscan.io/v2/api",
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
        api_key = self.get_secret("ETHERSCAN_API_KEY", os.getenv("ETHERSCAN_API_KEY"))
        api_url = self.get_params().get(
            "ETHERSCAN_API_URL", "https://api.etherscan.io/v2/api"
        )
        for d in data:
            try:
                transactions = await self._get_transactions(d.address, api_key, api_url)
                results.extend(transactions)
            except Exception as e:
                Logger.error(
                    self.sketch_id,
                    {"message": f"Error resolving transactions for {d.address}: {e}"},
                )
        return results

    async def _get_transactions(
        self, address: str, api_key: str, api_url: str
    ) -> List[Transaction]:
        transactions = []
        """Get transactions for a wallet address."""
        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
            "offset": 100,
            "sort": "asc",
            "apikey": api_key,
        }
        try:
            response = requests.get(api_url, params=params)

            # Raise an exception for HTTP errors (4xx or 5xx status codes)
            response.raise_for_status()

        except requests.exceptions.ConnectionError as e:
            raise ValueError(
                f"An error occurred connecting to {api_url}: Connection failed - {str(e)}"
            )
        except requests.exceptions.Timeout as e:
            raise ValueError(
                f"An error occurred fetching {api_url}: Request timeout - {str(e)}"
            )
        except requests.exceptions.RequestException as e:
            raise ValueError(f"An error occurred fetching {api_url}: {str(e)}")

        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError as e:
            raise ValueError(
                f"An error occurred fetching {api_url}: Invalid JSON response - {str(e)}"
            )

        # Check if the API returned an error
        if data.get("status") != "1":
            error_message = data.get("message", "Unknown API error")
            raise ValueError(f"An error occurred fetching {api_url}: {error_message}")

        results = data.get("result", [])
        for tx in results:
            # Contract creation transactions have no "to"
            target_address = tx["to"] or tx["contractAddress"] or address
            transactions.append(
                Transaction(
                    transaction_id=tx["hash"],
                    source=CryptoWallet(address=tx["from"]),
                    target=CryptoWallet(address=target_address),
                    amount=wei_to_eth(tx["value"]),
                    currency="ETH",
                    timestamp=int(tx["timeStamp"]),
                    channel="crypto",
                    status="failed" if tx.get("isError") == "1" else "success",
                    fees=wei_to_eth(int(tx["gasUsed"]) * int(tx["gasPrice"])),
                    chain="ethereum",
                    block_number=int(tx["blockNumber"]),
                    contract_address=tx["contractAddress"] or None,
                    function_name=tx.get("functionName") or None,
                )
            )
        return transactions

    def postprocess(
        self, results: List[OutputType], original_input: List[InputType]
    ) -> List[OutputType]:
        if not self._graph_service:
            return results

        for tx in results:
            self.create_node(tx.source)
            self.create_node(tx.target)
            self.create_relationship(
                tx.source,
                tx.target,
                "TRANSACTION",
                properties=tx.edge_properties(),
                edge_key=tx.transaction_id,
            )
            timestamp_str = (
                tx.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                if tx.timestamp
                else "Unknown time"
            )
            self.log_graph_message(
                f"Transaction on {timestamp_str}: {tx.source.address} -> {tx.target.address} ({tx.caption})"
            )

        return results


# Make types available at module level for easy access
InputType = CryptoWalletAddressToTransactions.InputType
OutputType = CryptoWalletAddressToTransactions.OutputType
