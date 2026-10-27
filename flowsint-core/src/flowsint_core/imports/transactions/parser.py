"""
Turn table rows into Transactions according to a TransactionMapping.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from flowsint_types import (
    BankAccount,
    CreditCard,
    CryptoWallet,
    FlowsintType,
    Merchant,
    MobileMoneyAccount,
    Transaction,
)

from .mapping import AccountSide, TransactionMapping
from .table_reader import TableData

ACCOUNT_CLASSES = {
    "MobileMoneyAccount": MobileMoneyAccount,
    "BankAccount": BankAccount,
    "CryptoWallet": CryptoWallet,
    "CreditCard": CreditCard,
    "Merchant": Merchant,
}
IDENTIFIER_FIELD = {
    "MobileMoneyAccount": "phone_number",
    "BankAccount": "account_number",
    "CryptoWallet": "address",
    "CreditCard": "card_number",
    "Merchant": "name",
}
PROVIDER_FIELD = {
    "MobileMoneyAccount": "provider",
    "BankAccount": "bank_name",
    "CreditCard": "issuer",
    "Merchant": "provider",
}
HOLDER_FIELD = {
    "MobileMoneyAccount": "account_holder",
    "BankAccount": "account_holder",
    "CreditCard": "cardholder_name",
}
COUNTRY_TYPES = {"MobileMoneyAccount", "BankAccount", "Merchant"}

DAY_FIRST_FORMATS = [
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
    "%d-%m-%Y",
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y",
    "%d/%m/%y %H:%M",
    "%d/%m/%y",
]
MONTH_FIRST_FORMATS = [
    f.replace("%d", "\0").replace("%m", "%d").replace("\0", "%m")
    for f in DAY_FIRST_FORMATS
]
YEAR_FIRST_FORMATS = ["%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d"]


@dataclass
class RowError:
    row: int  # line number in the original file
    message: str


@dataclass
class ParseOutcome:
    transactions: List[Transaction] = field(default_factory=list)
    errors: List[RowError] = field(default_factory=list)
    skipped_empty: int = 0


def cell_str(value: Any) -> Optional[str]:
    """Cell value as a clean string; Excel turns long numbers into floats."""
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    return text or None


def parse_amount(value: Any, decimal_separator: Optional[str] = None) -> float:
    """Parse "1 500,50", "1.500,50", "1,500.50", "(200)", "-200 XOF", 12.5..."""
    if isinstance(value, bool):
        raise ValueError(f"invalid amount: {value!r}")
    if isinstance(value, (int, float)):
        return float(value)
    text = cell_str(value)
    if text is None:
        raise ValueError("empty amount")

    negative = text.startswith("(") and text.endswith(")")
    cleaned = re.sub(r"[^\d,.\-]", "", text)
    if cleaned.count("-"):
        negative = negative or cleaned.startswith("-") or cleaned.endswith("-")
        cleaned = cleaned.replace("-", "")
    if not re.search(r"\d", cleaned):
        raise ValueError(f"invalid amount: {text!r}")

    sep = decimal_separator or _guess_decimal_separator(cleaned)
    thousands = "." if sep == "," else ","
    cleaned = cleaned.replace(thousands, "")
    if sep:
        cleaned = cleaned.replace(sep, ".")
    try:
        number = float(cleaned)
    except ValueError:
        raise ValueError(f"invalid amount: {text!r}")
    return -number if negative else number


def _guess_decimal_separator(s: str) -> Optional[str]:
    if "," in s and "." in s:
        return "," if s.rfind(",") > s.rfind(".") else "."
    if "," in s:
        if s.count(",") > 1:
            return None  # 1,234,567 -> thousands only
        # "1,500" -> thousands (common for XOF/XAF amounts), "12,5" -> decimal
        return None if len(s.split(",")[1]) == 3 else ","
    if "." in s:
        return None if s.count(".") > 1 else "."
    return None


def parse_date(
    value: Any, date_format: Optional[str] = None, day_first: bool = True
) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # Unix epoch, in milliseconds when too large for seconds
        seconds = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc)

    text = cell_str(value)
    if text is None:
        raise ValueError("empty date")
    if date_format:
        try:
            return datetime.strptime(text, date_format)
        except ValueError:
            raise ValueError(f"date {text!r} does not match format {date_format!r}")
    if text.isdigit():
        return parse_date(int(text))
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    formats = (
        DAY_FIRST_FORMATS if day_first else MONTH_FIRST_FORMATS
    ) + YEAR_FIRST_FORMATS
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"unrecognized date: {text!r}")


def build_account(side: AccountSide, row: Dict[str, Any]) -> FlowsintType:
    identifier = cell_str(row.get(side.column)) if side.column else None
    identifier = identifier or side.value
    if not identifier:
        raise ValueError(
            f"missing {side.account_type} identifier"
            + (f" in column {side.column!r}" if side.column else "")
        )

    data: Dict[str, Any] = {IDENTIFIER_FIELD[side.account_type]: identifier}
    provider_field = PROVIDER_FIELD.get(side.account_type)
    provider = (
        cell_str(row.get(side.provider_column)) if side.provider_column else None
    ) or side.provider
    if provider_field and provider:
        data[provider_field] = provider
    holder_field = HOLDER_FIELD.get(side.account_type)
    holder = cell_str(row.get(side.holder_column)) if side.holder_column else None
    if holder_field and holder:
        data[holder_field] = holder
    if side.account_type in COUNTRY_TYPES and side.country:
        data["country"] = side.country
    return ACCOUNT_CLASSES[side.account_type](**data)


def _optional_amount(value: Any, mapping: TransactionMapping) -> Optional[float]:
    return (
        None
        if cell_str(value) is None
        else parse_amount(value, mapping.decimal_separator)
    )


def _row_fingerprint(row: Dict[str, Any]) -> str:
    payload = json.dumps(
        [cell_str(v) for v in row.values()], ensure_ascii=False, default=str
    )
    return hashlib.sha1(payload.encode()).hexdigest()[:16]


def parse_transactions(table: TableData, mapping: TransactionMapping) -> ParseOutcome:
    outcome = ParseOutcome()
    outgoing_values = {v.strip().lower() for v in mapping.outgoing_values}
    seen_fingerprints: Dict[str, int] = {}

    for line, row in zip(table.line_numbers, table.rows):
        if all(cell_str(v) is None for v in row.values()):
            outcome.skipped_empty += 1
            continue
        try:
            if mapping.mode == "ledger":
                source = build_account(mapping.source, row)
                target = build_account(mapping.target, row)
                amount = abs(
                    parse_amount(
                        row.get(mapping.amount_column), mapping.decimal_separator
                    )
                )
            else:
                owner = build_account(mapping.owner, row)
                counterparty = build_account(mapping.counterparty, row)
                outgoing, amount = _statement_direction(row, mapping, outgoing_values)
                source, target = (
                    (owner, counterparty) if outgoing else (counterparty, owner)
                )

            if mapping.transaction_id_column and cell_str(
                row.get(mapping.transaction_id_column)
            ):
                transaction_id = cell_str(row.get(mapping.transaction_id_column))
            else:
                # Deterministic id so re-importing the same file doesn't duplicate;
                # the occurrence counter keeps identical rows distinct.
                fingerprint = _row_fingerprint(row)
                occurrence = seen_fingerprints.get(fingerprint, 0)
                seen_fingerprints[fingerprint] = occurrence + 1
                transaction_id = f"row-{fingerprint}-{occurrence}"

            timestamp = None
            if (
                mapping.date_column
                and cell_str(row.get(mapping.date_column)) is not None
            ):
                timestamp = parse_date(
                    row.get(mapping.date_column), mapping.date_format, mapping.day_first
                )

            currency = (
                cell_str(row.get(mapping.currency_column))
                if mapping.currency_column
                else None
            ) or mapping.currency

            outcome.transactions.append(
                Transaction(
                    transaction_id=transaction_id,
                    source=source,
                    target=target,
                    amount=amount,
                    currency=currency,
                    timestamp=timestamp,
                    channel=mapping.channel,
                    status=cell_str(row.get(mapping.status_column))
                    if mapping.status_column
                    else None,
                    fees=_optional_amount(row.get(mapping.fees_column), mapping)
                    if mapping.fees_column
                    else None,
                    description=cell_str(row.get(mapping.description_column))
                    if mapping.description_column
                    else None,
                    country=mapping.country,
                )
            )
        except Exception as e:
            outcome.errors.append(RowError(row=line, message=str(e)))

    return outcome


def _statement_direction(
    row: Dict[str, Any], mapping: TransactionMapping, outgoing_values: set
) -> tuple[bool, float]:
    """Return (outgoing from the owner?, absolute amount)."""
    if mapping.debit_column or mapping.credit_column:
        debit = (
            _optional_amount(row.get(mapping.debit_column), mapping)
            if mapping.debit_column
            else None
        )
        credit = (
            _optional_amount(row.get(mapping.credit_column), mapping)
            if mapping.credit_column
            else None
        )
        if debit:
            return True, abs(debit)
        if credit:
            return False, abs(credit)
        if not mapping.amount_column:
            raise ValueError("no debit or credit amount")

    amount = parse_amount(row.get(mapping.amount_column), mapping.decimal_separator)
    if mapping.direction_column:
        direction = (cell_str(row.get(mapping.direction_column)) or "").lower()
        return direction in outgoing_values, abs(amount)
    return amount < 0, abs(amount)
