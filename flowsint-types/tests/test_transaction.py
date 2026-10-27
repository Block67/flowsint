from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from flowsint_types import (
    BankAccount,
    CryptoWallet,
    Merchant,
    MobileMoneyAccount,
    Transaction,
    get_type,
)


class TestMobileMoneyAccount:
    def test_local_number_normalized_with_country(self):
        account = MobileMoneyAccount(
            phone_number="77 123 45 67", country="SN", provider="Wave"
        )
        assert account.phone_number == "+221771234567"
        assert account.nodeLabel == "+221771234567 (Wave)"

    def test_international_number_normalized(self):
        account = MobileMoneyAccount(phone_number="+221 77 123 45 67")
        assert account.phone_number == "+221771234567"
        assert account.nodeLabel == "+221771234567"

    def test_unparseable_number_kept_cleaned(self):
        account = MobileMoneyAccount(phone_number="12-34 5")
        assert account.phone_number == "12345"

    def test_from_string(self):
        account = MobileMoneyAccount.model_validate("+221771234567")
        assert account.phone_number == "+221771234567"


class TestMerchant:
    def test_label_with_merchant_id(self):
        assert Merchant(name="Shop", merchant_id="M42").nodeLabel == "Shop [M42]"

    def test_label_without_merchant_id(self):
        assert Merchant(name="Shop").nodeLabel == "Shop"


class TestAccountLabels:
    def test_bank_accounts_with_same_last_digits_do_not_collide(self):
        a = BankAccount(account_number="111111234", bank_name="BICIS")
        b = BankAccount(account_number="222221234", bank_name="BICIS")
        assert a.nodeLabel != b.nodeLabel


def make_tx(**overrides):
    data = {
        "transaction_id": "tx-1",
        "source": CryptoWallet(address="0x" + "a" * 40),
        "target": MobileMoneyAccount(phone_number="+221771234567", provider="Wave"),
        "amount": 1500.5,
        "currency": "xof",
    }
    data.update(overrides)
    return Transaction(**data)


class TestTransaction:
    def test_registered(self):
        assert get_type("Transaction") is Transaction

    def test_label_is_transaction_id(self):
        assert make_tx().nodeLabel == "tx-1"

    def test_currency_uppercased(self):
        assert make_tx().currency == "XOF"

    def test_accounts_resolved_from_dicts(self):
        tx = make_tx(
            source={"address": "0x" + "b" * 40},
            target={"phone_number": "+221771234567", "provider": "Orange Money"},
        )
        assert isinstance(tx.source, CryptoWallet)
        assert isinstance(tx.target, MobileMoneyAccount)

    def test_non_account_endpoint_rejected(self):
        with pytest.raises(ValidationError):
            make_tx(target={"foo": "bar"})

    def test_epoch_timestamp_is_utc(self):
        tx = make_tx(timestamp=1700000000)
        assert tx.timestamp == datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc)

    def test_naive_timestamp_assumed_utc(self):
        tx = make_tx(timestamp="2024-01-02T03:04:05")
        assert tx.timestamp.tzinfo == timezone.utc

    def test_caption(self):
        assert make_tx().caption == "1,500.5 XOF"
        assert make_tx(amount=0.25, currency=None).caption == "0.25"

    def test_edge_properties(self):
        tx = make_tx(timestamp=1700000000, channel="crypto", block_number=123)
        props = tx.edge_properties()
        assert props["transaction_id"] == "tx-1"
        assert props["amount"] == 1500.5
        assert props["currency"] == "XOF"
        assert props["timestamp"] == "2023-11-14T22:13:20+00:00"
        assert props["timestamp_epoch"] == 1700000000
        assert props["date"] == props["timestamp"]
        assert props["caption"] == "1,500.5 XOF"
        assert props["weight"] == 1500.5
        assert props["block_number"] == 123
        assert "fees" not in props  # None values are dropped
        assert all(isinstance(v, (str, int, float, bool)) for v in props.values())

    def test_weight_prefers_usd(self):
        assert make_tx(amount_usd=2.5).edge_properties()["weight"] == 2.5
