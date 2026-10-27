"""Bitcoin, TRON, ERC-20 and OFAC enrichers, with responses shaped like the
real APIs (mempool.space, TronGrid, Etherscan v2, 0xB10C OFAC lists)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from flowsint_enrichers.crypto.to_btc_transactions import (
    CryptoWalletToBtcTransactions,
    utxo_transfers,
)
from flowsint_enrichers.crypto.to_sanctions import CryptoWalletToSanctions
from flowsint_enrichers.crypto.to_token_transfers import CryptoWalletToTokenTransfers
from flowsint_enrichers.crypto.to_trc20_transfers import (
    USDT_TRC20,
    CryptoWalletToTrc20Transfers,
)
from flowsint_types import CryptoWallet

ME = "bc1qme0000000000000000000000000000000000000"
PARTNER = "bc1qpartner000000000000000000000000000000"
SHOP = "1ShopShopShopShopShopShopShopShop"
CHANGE_ALT = "3Change2222222222222222222222222"


def response(body):
    r = MagicMock()
    r.json.return_value = body
    r.text = body if isinstance(body, str) else ""
    return r


def btc_tx(txid, inputs, outputs, confirmed=True):
    return {
        "txid": txid,
        "vin": [
            {
                "is_coinbase": False,
                "prevout": {"scriptpubkey_address": a, "value": v},
            }
            for a, v in inputs
        ],
        "vout": [{"scriptpubkey_address": a, "value": v} for a, v in outputs]
        + [{"scriptpubkey_type": "op_return", "value": 0}],
        "status": (
            {"confirmed": True, "block_time": 1700000000, "block_height": 800000}
            if confirmed
            else {"confirmed": False}
        ),
    }


class TestUtxoTransfers:
    def test_spend_excludes_change(self):
        tx = btc_tx("t1", [(ME, 100_000)], [(SHOP, 60_000), (ME, 39_000)])
        (transfer,) = utxo_transfers(tx, ME)

        assert (transfer.source.address, transfer.target.address) == (ME, SHOP)
        assert transfer.amount == 0.0006
        assert transfer.currency == "BTC"
        assert transfer.transaction_id == f"t1:{ME}:{SHOP}"
        assert transfer.source.chain == "bitcoin"
        assert transfer.timestamp == datetime(
            2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc
        )
        assert transfer.edge_properties()["tx_hash"] == "t1"

    def test_spend_with_other_inputs_is_proportional(self):
        tx = btc_tx("t2", [(ME, 75_000), (PARTNER, 25_000)], [(SHOP, 100_000)])
        (transfer,) = utxo_transfers(tx, ME)
        assert transfer.amount == 0.00075

    def test_receive_credits_each_input_proportionally(self):
        tx = btc_tx(
            "t3",
            [(PARTNER, 30_000), (CHANGE_ALT, 10_000)],
            [(ME, 20_000), (SHOP, 19_000)],
        )
        transfers = {t.source.address: t.amount for t in utxo_transfers(tx, ME)}
        assert transfers == {PARTNER: 0.00015, CHANGE_ALT: 0.00005}

    def test_pending_has_no_timestamp(self):
        tx = btc_tx("t4", [(PARTNER, 1000)], [(ME, 900)], confirmed=False)
        (transfer,) = utxo_transfers(tx, ME)
        assert transfer.timestamp is None
        assert transfer.status == "pending"

    def test_coinbase_ignored(self):
        tx = {"txid": "cb", "vin": [{"is_coinbase": True}], "vout": [], "status": {}}
        assert utxo_transfers(tx, ME) == []


class TestBtcEnricher:
    @pytest.mark.asyncio
    async def test_paginates_on_last_confirmed_txid(self):
        enricher = CryptoWalletToBtcTransactions(
            sketch_id="s", scan_id="x", params={"MAX_PAGES": "2"}
        )
        page1 = [btc_tx(f"a{i}", [(PARTNER, 10)], [(ME, 9)]) for i in range(25)]
        page2 = [btc_tx("b0", [(PARTNER, 10)], [(ME, 9)])]
        with patch(
            "requests.get", side_effect=[response(page1), response(page2)]
        ) as get:
            out = await enricher.scan([CryptoWallet(address=ME)])

        assert len(out) == 26
        assert get.call_args_list[1].args[0].endswith(f"/address/{ME}/txs/chain/a24")

    @pytest.mark.asyncio
    async def test_skips_non_bitcoin(self):
        enricher = CryptoWalletToBtcTransactions(sketch_id="s", scan_id="x")
        with patch("requests.get") as get:
            assert await enricher.scan([CryptoWallet(address="0x" + "a" * 40)]) == []
        get.assert_not_called()


TRON_ME = "TWd4WrZ9wn84f5x1hZhL4DHvk738ns5jwb"
TRON_OTHER = "TDqSquXBgUCLYvYC4XZgrprLK589dkhSCf"


def trc20_row(txid, value="4050000"):
    return {
        "transaction_id": txid,
        "token_info": {
            "symbol": "USDT",
            "address": USDT_TRC20,
            "decimals": 6,
            "name": "Tether USD",
        },
        "block_timestamp": 1792645392000,
        "from": TRON_OTHER,
        "to": TRON_ME,
        "type": "Transfer",
        "value": value,
    }


class TestTrc20Enricher:
    @pytest.mark.asyncio
    async def test_usdt_transfers_and_pagination(self):
        enricher = CryptoWalletToTrc20Transfers(
            sketch_id="s", scan_id="x", params={"MAX_TRANSACTIONS": "3"}
        )
        page1 = {
            "success": True,
            "data": [trc20_row("t1"), trc20_row("t2")],
            "meta": {"links": {"next": "https://api.trongrid.io/next-page"}},
        }
        page2 = {
            "success": True,
            "data": [trc20_row("t3"), trc20_row("t4")],
            "meta": {},
        }
        with patch(
            "requests.get", side_effect=[response(page1), response(page2)]
        ) as get:
            out = await enricher.scan([CryptoWallet(address=TRON_ME)])

        assert [t.edge_properties()["tx_hash"] for t in out] == ["t1", "t2", "t3"]
        first = out[0]
        assert first.amount == 4.05
        assert first.currency == "USDT"
        assert first.source.chain == "tron"
        assert first.timestamp.year == 2026
        first_call, second_call = get.call_args_list
        assert first_call.kwargs["params"]["contract_address"] == USDT_TRC20
        assert second_call.args[0] == "https://api.trongrid.io/next-page"
        assert second_call.kwargs["params"] is None
        assert "TRON-PRO-API-KEY" not in first_call.kwargs["headers"]

    @pytest.mark.asyncio
    async def test_empty_contract_means_all_tokens(self):
        enricher = CryptoWalletToTrc20Transfers(
            sketch_id="s", scan_id="x", params={"TOKEN_CONTRACT": ""}
        )
        with patch(
            "requests.get", return_value=response({"success": True, "data": []})
        ) as get:
            await enricher.scan([CryptoWallet(address=TRON_ME)])
        assert "contract_address" not in get.call_args.kwargs["params"]


class TestTokenTransfers:
    def test_erc20_amount_uses_token_decimals(self):
        enricher = CryptoWalletToTokenTransfers(sketch_id="s", scan_id="x")
        row = {
            "hash": "0xh",
            "from": "0x" + "a" * 40,
            "to": "0x" + "b" * 40,
            "value": "2500000",
            "tokenDecimal": "6",
            "tokenSymbol": "USDT",
            "contractAddress": "0xdac17f958d2ee523a2206206994597c13d831ec7",
            "timeStamp": "1700000000",
            "blockNumber": "1",
        }
        with patch(
            "requests.get", return_value=response({"status": "1", "result": [row]})
        ) as get:
            (tx,) = enricher._get_transfers(
                "0x" + "a" * 40, "k", "https://api", "1", row["contractAddress"], 100
            )

        assert tx.amount == 2.5
        assert tx.currency == "USDT"
        assert tx.transaction_id.startswith("0xh:")
        params = get.call_args.kwargs["params"]
        assert params["action"] == "tokentx"
        assert params["contractaddress"] == row["contractAddress"]


OFAC_ETH = "0x0330070FD38Ec3bB94F58FA55D40368271E9e54A\n0x1111111111111111111111111111111111111111\n"


class TestSanctions:
    @pytest.mark.asyncio
    async def test_evm_match_is_case_insensitive(self):
        enricher = CryptoWalletToSanctions(sketch_id="s", scan_id="x")
        empty = response("")
        with patch(
            "requests.get", side_effect=[response(OFAC_ETH)] + [empty] * 5
        ) as get:
            out = await enricher.scan(
                [CryptoWallet(address="0x0330070fd38ec3bb94f58fa55d40368271e9e54a")]
            )

        (profile,) = out
        assert profile.risk_level == "critical"
        assert profile.risk_factors == ["OFAC SDN sanctioned address (ETH)"]
        assert get.call_args_list[0].args[0].endswith("sanctioned_addresses_ETH.txt")

    @pytest.mark.asyncio
    async def test_lists_downloaded_once_per_run(self):
        enricher = CryptoWalletToSanctions(sketch_id="s", scan_id="x")
        with patch("requests.get", return_value=response("")) as get:
            await enricher.scan(
                [
                    CryptoWallet(address="0x" + "a" * 40),
                    CryptoWallet(address="0x" + "b" * 40),
                ]
            )
        assert get.call_count == 6  # ETH, USDT, USDC, BSC, ARB, ETC

    @pytest.mark.asyncio
    async def test_bitcoin_checks_xbt_list_only(self):
        enricher = CryptoWalletToSanctions(sketch_id="s", scan_id="x")
        with patch("requests.get", return_value=response(f"{ME}\n")) as get:
            out = await enricher.scan([CryptoWallet(address=ME)])
        assert len(out) == 1
        assert get.call_count == 1
        assert get.call_args.args[0].endswith("sanctioned_addresses_XBT.txt")

    def test_postprocess_links_wallet_to_profile(self):
        enricher = CryptoWalletToSanctions(sketch_id="s", scan_id="x")
        enricher._graph_service = MagicMock()
        wallet = CryptoWallet(address=ME)
        from flowsint_types import RiskProfile

        profile = RiskProfile(entity_id=ME, risk_level="critical")
        enricher.postprocess([profile], [wallet])

        rel = enricher._graph_service.create_relationship.call_args.kwargs
        assert rel["rel_label"] == "HAS_RISK_PROFILE"
        assert rel["from_obj"] is wallet
