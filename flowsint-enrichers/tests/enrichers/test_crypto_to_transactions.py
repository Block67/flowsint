from unittest.mock import MagicMock, patch

import pytest

from flowsint_enrichers.crypto.to_transactions import CryptoWalletAddressToTransactions
from flowsint_types import CryptoWallet, Transaction

WALLET = "0x" + "a" * 40
OTHER = "0x" + "b" * 40
CONTRACT = "0x" + "c" * 40


def etherscan_tx(**overrides):
    tx = {
        "hash": "0xhash1",
        "from": WALLET,
        "to": OTHER,
        "value": str(2 * 10**18),
        "timeStamp": "1700000000",
        "blockNumber": "100",
        "gasUsed": "21000",
        "gasPrice": str(10**9),
        "isError": "0",
        "contractAddress": "",
        "functionName": "",
    }
    tx.update(overrides)
    return tx


@pytest.fixture
def enricher():
    e = CryptoWalletAddressToTransactions(sketch_id="sketch-1", scan_id="scan-1")
    e._graph_service = MagicMock()
    return e


def mock_response(results):
    response = MagicMock()
    response.json.return_value = {"status": "1", "result": results}
    return response


def test_get_transactions_maps_etherscan_fields(enricher):
    results = [
        etherscan_tx(),
        etherscan_tx(hash="0xhash2", to=None, contractAddress=CONTRACT, isError="1"),
    ]
    with patch("requests.get", return_value=mock_response(results)) as get:
        txs = enricher._get_transactions(WALLET, "key", "https://api", "1", 100)

    # Etherscan v2 rejects requests without a chain id
    assert get.call_args.kwargs["params"]["chainid"] == "1"

    assert [tx.transaction_id for tx in txs] == ["0xhash1", "0xhash2"]
    first = txs[0]
    assert isinstance(first, Transaction)
    assert first.source.address == WALLET
    assert first.target.address == OTHER
    assert first.amount == 2.0
    assert first.currency == "ETH"
    assert first.channel == "crypto"
    assert first.status == "success"
    assert first.fees == pytest.approx(21000 * 10**9 / 10**18)
    assert first.edge_properties()["block_number"] == 100
    # Contract creation: no "to", target falls back to the created contract
    assert txs[1].target.address == CONTRACT
    assert txs[1].status == "failed"


def test_postprocess_creates_one_edge_per_transaction(enricher):
    txs = [
        Transaction(
            transaction_id=h,
            source=CryptoWallet(address=WALLET),
            target=CryptoWallet(address=OTHER),
            amount=1.0,
            currency="ETH",
            timestamp=1700000000,
        )
        for h in ("0xhash1", "0xhash2")
    ]

    enricher.postprocess(txs, [CryptoWallet(address=WALLET)])

    graph = enricher._graph_service
    assert graph.create_node_from_flowsint_type.call_count == 4
    rel_calls = graph.create_relationship.call_args_list
    assert [c.kwargs["edge_key"] for c in rel_calls] == ["0xhash1", "0xhash2"]
    assert all(c.kwargs["rel_label"] == "TRANSACTION" for c in rel_calls)
    assert rel_calls[0].kwargs["properties"]["caption"] == "1 ETH"


def test_other_evm_chain_sets_currency_and_chain(enricher):
    with patch("requests.get", return_value=mock_response([etherscan_tx()])):
        (tx,) = enricher._get_transactions(WALLET, "key", "https://api", "56", 100)

    assert tx.currency == "BNB"
    assert tx.source.chain == "bsc"


def test_no_transactions_is_not_an_error(enricher):
    response = MagicMock()
    response.json.return_value = {
        "status": "0",
        "message": "No transactions found",
        "result": [],
    }
    with patch("requests.get", return_value=response):
        assert enricher._get_transactions(WALLET, "key", "https://api", "1", 100) == []


def test_api_error_is_raised(enricher):
    response = MagicMock()
    response.json.return_value = {
        "status": "0",
        "message": "NOTOK",
        "result": "Missing chainid parameter",
    }
    with patch("requests.get", return_value=response):
        with pytest.raises(ValueError, match="Missing chainid"):
            enricher._get_transactions(WALLET, "key", "https://api", "1", 100)


@pytest.mark.asyncio
async def test_scan_skips_non_evm_wallets(enricher):
    with patch("requests.get") as get:
        out = await enricher.scan(
            [CryptoWallet(address="TWd4WrZ9wn84f5x1hZhL4DHvk738ns5jwb")]
        )
    assert out == []
    get.assert_not_called()
