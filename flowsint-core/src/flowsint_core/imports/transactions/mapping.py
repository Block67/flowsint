"""
Column mapping describing how a statement's columns become Transactions.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from flowsint_types.transaction import TransactionChannel

AccountType = Literal[
    "MobileMoneyAccount", "BankAccount", "CryptoWallet", "CreditCard", "Merchant"
]

# Values of a direction column meaning "money leaves the statement owner".
DEFAULT_OUTGOING_VALUES = [
    "debit",
    "dr",
    "d",
    "out",
    "outgoing",
    "sortant",
    "sortie",
    "envoi",
    "retrait",
    "withdrawal",
    "paiement",
    "payment",
    "transfert sortant",
]


class AccountSide(BaseModel):
    """Where to read one side of the transaction (an account)."""

    account_type: AccountType
    column: Optional[str] = Field(
        None, description="Column holding the account identifier"
    )
    value: Optional[str] = Field(
        None, description="Fixed identifier (e.g. the statement owner's account)"
    )
    provider_column: Optional[str] = None
    provider: Optional[str] = Field(
        None, description="Fixed provider / bank / issuer name"
    )
    holder_column: Optional[str] = None
    country: Optional[str] = Field(
        None, description="ISO country code, used to normalize local phone numbers"
    )

    @model_validator(mode="after")
    def check_identifier(self) -> "AccountSide":
        if not self.column and not self.value:
            raise ValueError("an account needs either a column or a fixed value")
        return self


class TransactionMapping(BaseModel):
    """
    mode="ledger": every row has its own source and target accounts.
    mode="statement": rows belong to one owner account; the counterparty is per
    row and the direction comes from the amount sign, debit/credit columns or
    a direction column.
    """

    mode: Literal["ledger", "statement"] = "ledger"

    source: Optional[AccountSide] = None
    target: Optional[AccountSide] = None
    owner: Optional[AccountSide] = None
    counterparty: Optional[AccountSide] = None

    transaction_id_column: Optional[str] = None
    date_column: Optional[str] = None
    date_format: Optional[str] = Field(
        None, description="strptime format; auto-detected when empty"
    )
    day_first: bool = Field(
        True,
        description="Read 01/02/2024 as 1 February (FR/Africa) instead of 2 January",
    )

    amount_column: Optional[str] = None
    debit_column: Optional[str] = None
    credit_column: Optional[str] = None
    direction_column: Optional[str] = None
    outgoing_values: List[str] = Field(
        default_factory=lambda: list(DEFAULT_OUTGOING_VALUES)
    )
    decimal_separator: Optional[Literal[",", "."]] = Field(
        None, description="Auto-detected per value when empty"
    )

    currency_column: Optional[str] = None
    currency: Optional[str] = None
    fees_column: Optional[str] = None
    status_column: Optional[str] = None
    description_column: Optional[str] = None
    channel: Optional[TransactionChannel] = None
    country: Optional[str] = None

    @model_validator(mode="after")
    def check_mode(self) -> "TransactionMapping":
        if self.mode == "ledger":
            if not self.source or not self.target:
                raise ValueError("ledger mode needs a source and a target account")
            if not self.amount_column:
                raise ValueError("ledger mode needs an amount column")
        else:
            if not self.owner or not self.counterparty:
                raise ValueError(
                    "statement mode needs an owner and a counterparty account"
                )
            if not self.amount_column and not (self.debit_column or self.credit_column):
                raise ValueError(
                    "statement mode needs an amount column or debit/credit columns"
                )
        return self
