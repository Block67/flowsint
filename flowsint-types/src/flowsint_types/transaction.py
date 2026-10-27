from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional, Self, Union

from pydantic import Field, field_validator, model_validator

from .bank_account import BankAccount
from .credit_card import CreditCard
from .flowsint_base import FlowsintType
from .merchant import Merchant
from .mobile_money_account import MobileMoneyAccount
from .registry import flowsint_type
from .wallet import CryptoWallet

# Anything money can move between. People and organizations own accounts
# (OWNS edges); they are not transaction endpoints themselves.
Account = Union[CryptoWallet, MobileMoneyAccount, BankAccount, CreditCard, Merchant]

TransactionChannel = Literal["bank", "mobile_money", "card", "crypto", "cash", "other"]


@flowsint_type
class Transaction(FlowsintType):
    """A movement of money from one account to another, on any channel.

    Stored in the graph as a TRANSACTION relationship between the source and
    target account nodes (see `edge_properties`), not as a node, so that money
    flows can be followed with path queries.
    """

    transaction_id: str = Field(
        ...,
        description="Unique transaction identifier (reference, hash...)",
        title="Transaction ID",
        json_schema_extra={"primary": True},
    )
    source: Account = Field(..., description="Debited account", title="Source")
    target: Account = Field(..., description="Credited account", title="Target")
    amount: float = Field(
        ..., description="Amount in the transaction currency", title="Amount"
    )
    currency: Optional[str] = Field(
        None,
        description="Currency code (ISO 4217) or crypto ticker",
        title="Currency",
    )
    amount_usd: Optional[float] = Field(
        None, description="Amount converted to USD", title="Amount USD"
    )
    timestamp: Optional[datetime] = Field(
        None,
        description="When the transaction happened (ISO 8601 or unix epoch)",
        title="Timestamp",
    )
    channel: Optional[TransactionChannel] = Field(
        None, description="Payment channel", title="Channel"
    )
    status: Optional[str] = Field(
        None, description="Status (success, failed, pending...)", title="Status"
    )
    fees: Optional[float] = Field(
        None, description="Fees in the transaction currency", title="Fees"
    )
    description: Optional[str] = Field(
        None, description="Free-text label or memo", title="Description"
    )
    country: Optional[str] = Field(
        None, description="Country code (ISO 3166-1 alpha-2)", title="Country Code"
    )

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().upper() if v else v

    @field_validator("timestamp")
    @classmethod
    def ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Naive datetimes are assumed UTC so ISO strings sort chronologically."""
        if v is None:
            return v
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @model_validator(mode="after")
    def compute_label(self) -> Self:
        self.nodeLabel = self.transaction_id
        return self

    @property
    def caption(self) -> str:
        amount = f"{self.amount:,.8f}".rstrip("0").rstrip(".")
        return f"{amount} {self.currency}" if self.currency else amount

    def edge_properties(self) -> Dict[str, Any]:
        """Flat, Neo4j-storable properties for the TRANSACTION relationship.

        `caption`, `date` and `weight` are the fields the graph UI reads on edges.
        Extra primitive fields (e.g. block_number for on-chain transactions) are
        kept as-is.
        """
        props: Dict[str, Any] = {
            "type": "transaction",
            "transaction_id": self.transaction_id,
            "amount": self.amount,
            "currency": self.currency,
            "amount_usd": self.amount_usd,
            "channel": self.channel,
            "status": self.status,
            "fees": self.fees,
            "description": self.description,
            "country": self.country,
            "caption": self.caption,
            "weight": self.amount_usd if self.amount_usd is not None else self.amount,
        }
        if self.timestamp is not None:
            props["timestamp"] = self.timestamp.isoformat()
            props["timestamp_epoch"] = int(self.timestamp.timestamp())
            props["date"] = props["timestamp"]
        for key, value in (self.model_extra or {}).items():
            if isinstance(value, (str, int, float, bool)):
                props.setdefault(key, value)
        return {k: v for k, v in props.items() if v is not None}
