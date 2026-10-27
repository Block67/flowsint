from datetime import date
from typing import Any, Dict, List, Optional, Set

import requests

from flowsint_core.core.enricher_base import Enricher
from flowsint_core.core.logger import Logger
from flowsint_enrichers.crypto._common import REQUEST_TIMEOUT
from flowsint_enrichers.registry import flowsint_enricher
from flowsint_types.risk_profile import RiskProfile
from flowsint_types.wallet import CryptoWallet

OFAC_LISTS_URL = "https://raw.githubusercontent.com/0xB10C/ofac-sanctioned-digital-currency-addresses/lists"
SOURCE = (
    "OFAC SDN list (via github.com/0xB10C/ofac-sanctioned-digital-currency-addresses)"
)

# Which list files to check for an address, by chain. Lists are per asset as
# published by OFAC; EVM addresses are shared across EVM chains.
LISTS_BY_CHAIN = {
    "bitcoin": ["XBT"],
    "tron": ["TRX", "USDT"],
    "evm": ["ETH", "USDT", "USDC", "BSC", "ARB", "ETC"],
}


def chain_family(wallet: CryptoWallet) -> Optional[str]:
    if wallet.chain in ("bitcoin", "tron"):
        return wallet.chain
    if wallet.address.lower().startswith("0x"):
        return "evm"
    return None


def normalize(address: str, family: str) -> str:
    # EVM addresses are case-insensitive (checksum casing); base58 ones are not
    return address.strip().lower() if family == "evm" else address.strip()


@flowsint_enricher
class CryptoWalletToSanctions(Enricher):
    """[OFAC] Check whether a crypto address is on the OFAC SDN sanctions list."""

    InputType = CryptoWallet
    OutputType = RiskProfile

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
        self._lists: Dict[str, Set[str]] = {}

    @classmethod
    def icon(cls) -> str | None:
        return "cryptowallet"

    @classmethod
    def get_params_schema(cls) -> List[Dict[str, Any]]:
        return [
            {
                "name": "OFAC_LISTS_URL",
                "type": "url",
                "description": "Base URL of the sanctioned_addresses_<ASSET>.txt lists.",
                "required": False,
                "default": OFAC_LISTS_URL,
            }
        ]

    @classmethod
    def name(cls) -> str:
        return "cryptowallet_to_sanctions"

    @classmethod
    def category(cls) -> str:
        return "CryptoWallet"

    @classmethod
    def key(cls) -> str:
        return "address"

    def _load_list(self, base_url: str, asset: str, family: str) -> Set[str]:
        if asset not in self._lists:
            response = requests.get(
                f"{base_url}/sanctioned_addresses_{asset}.txt", timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            self._lists[asset] = {
                normalize(line, family)
                for line in response.text.splitlines()
                if line.strip()
            }
        return self._lists[asset]

    async def scan(self, data: List[InputType]) -> List[OutputType]:
        base_url = (self.get_params().get("OFAC_LISTS_URL") or OFAC_LISTS_URL).rstrip(
            "/"
        )
        results: List[OutputType] = []
        for wallet in data:
            family = chain_family(wallet)
            if family is None:
                Logger.warn(
                    self.sketch_id,
                    {"message": f"Unknown chain for {wallet.address}, skipped."},
                )
                continue
            try:
                address = normalize(wallet.address, family)
                hits = [
                    asset
                    for asset in LISTS_BY_CHAIN[family]
                    if address in self._load_list(base_url, asset, family)
                ]
            except Exception as e:
                Logger.error(
                    self.sketch_id,
                    {"message": f"Error checking sanctions for {wallet.address}: {e}"},
                )
                continue
            if not hits:
                Logger.info(
                    self.sketch_id,
                    {"message": f"{wallet.address} is not on the OFAC lists."},
                )
                continue
            results.append(
                RiskProfile(
                    entity_id=wallet.address,
                    entity_type="CryptoWallet",
                    risk_level="critical",
                    overall_risk_score=100,
                    risk_factors=[f"OFAC SDN sanctioned address ({', '.join(hits)})"],
                    compliance_risks=["Sanctions (OFAC SDN)"],
                    assessment_date=date.today().isoformat(),
                    source=SOURCE,
                )
            )
        return results

    def postprocess(
        self, results: List[OutputType], original_input: List[InputType]
    ) -> List[OutputType]:
        if not self._graph_service:
            return results
        wallets = {w.address: w for w in original_input}
        for profile in results:
            wallet = wallets.get(profile.entity_id) or CryptoWallet(
                address=profile.entity_id
            )
            self.create_node(wallet)
            self.create_node(profile)
            self.create_relationship(wallet, profile, "HAS_RISK_PROFILE")
            self.log_graph_message(f"{wallet.address} is on the OFAC sanctions list")
        return results


InputType = CryptoWalletToSanctions.InputType
OutputType = CryptoWalletToSanctions.OutputType
