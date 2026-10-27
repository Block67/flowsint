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


@flowsint_enricher
class CryptoWalletToTokenTransfers(Enricher):
    """[ETHERSCAN] Resolve ERC-20 token transfers (USDT, USDC...) for an EVM wallet."""

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
        return [
            {
                "name": "ETHERSCAN_API_KEY",
                "type": "vaultSecret",
                "description": "The Etherscan API key.",
                "required": True,
            },
            EVM_CHAIN_PARAM,
            {
                "name": "TOKEN_CONTRACT",
                "type": "string",
                "description": "Only this token contract (e.g. USDT). Empty = all tokens, including spam tokens.",
                "required": False,
            },
            {
                "name": "MAX_TRANSACTIONS",
                "type": "number",
                "description": "Most recent transfers to fetch per wallet (max 10000).",
                "required": False,
                "default": "100",
            },
            {
                "name": "ETHERSCAN_API_URL",
                "type": "url",
                "description": "The Etherscan API URL.",
                "required": False,
                "default": ETHERSCAN_V2_URL,
            },
        ]

    @classmethod
    def name(cls) -> str:
        return "cryptowallet_to_token_transfers"

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
        contract = (params.get("TOKEN_CONTRACT") or "").strip() or None
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
                    self._get_transfers(
                        d.address, api_key, api_url, chain_id, contract, limit
                    )
                )
            except Exception as e:
                Logger.error(
                    self.sketch_id,
                    {
                        "message": f"Error resolving token transfers for {d.address}: {e}"
                    },
                )
        return results

    def _get_transfers(
        self,
        address: str,
        api_key: str,
        api_url: str,
        chain_id: str,
        contract: Optional[str],
        limit: int,
    ) -> List[Transaction]:
        chain = EVM_CHAINS.get(chain_id, (f"evm-{chain_id}",))[0]
        query: Dict[str, Any] = {
            "chainid": chain_id,
            "module": "account",
            "action": "tokentx",
            "address": address,
            "page": 1,
            "offset": limit,
            "sort": "desc",
            "apikey": api_key,
        }
        if contract:
            query["contractaddress"] = contract
        transfers = []
        for tx in etherscan_get(api_url, query):
            # A transaction can move several tokens / to several recipients
            transfer_id = f"{tx['hash']}:{tx['contractAddress']}:{tx['from']}:{tx['to']}:{tx['value']}"
            transfers.append(
                Transaction(
                    transaction_id=transfer_id,
                    source=CryptoWallet(address=tx["from"], chain=chain),
                    target=CryptoWallet(address=tx["to"], chain=chain),
                    amount=to_units(tx["value"], int(tx.get("tokenDecimal") or 0)),
                    currency=tx.get("tokenSymbol") or None,
                    timestamp=int(tx["timeStamp"]),
                    channel="crypto",
                    chain=chain,
                    tx_hash=tx["hash"],
                    token_contract=tx["contractAddress"],
                    block_number=int(tx["blockNumber"]),
                )
            )
        return transfers

    def postprocess(
        self, results: List[OutputType], original_input: List[InputType]
    ) -> List[OutputType]:
        if self._graph_service:
            write_transactions(self, results)
        return results


InputType = CryptoWalletToTokenTransfers.InputType
OutputType = CryptoWalletToTokenTransfers.OutputType
