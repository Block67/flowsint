from typing import Any, Optional, Self

import phonenumbers
from phonenumbers import NumberParseException
from pydantic import Field, model_validator

from .flowsint_base import FlowsintType
from .registry import flowsint_type


@flowsint_type
class MobileMoneyAccount(FlowsintType):
    """Represents a mobile money wallet (Orange Money, MTN MoMo, Wave, M-Pesa...).

    The same phone number can hold wallets at several providers (e.g. Wave on
    an Orange line), so the graph identity is phone number + provider. Always
    set the provider when it is known, otherwise the same wallet ends up as two
    nodes.
    """

    phone_number: str = Field(
        ...,
        description="Phone number the wallet is attached to (normalized to E.164 when possible)",
        title="Phone Number",
        json_schema_extra={"primary": True},
    )
    provider: Optional[str] = Field(
        None,
        description="Mobile money provider (Orange Money, MTN MoMo, Wave, Moov, M-Pesa...)",
        title="Provider",
    )
    country: Optional[str] = Field(
        None, description="Country code (ISO 3166-1 alpha-2)", title="Country Code"
    )
    account_holder: Optional[str] = Field(
        None, description="Registered holder name (KYC)", title="Account Holder"
    )
    account_type: Optional[str] = Field(
        None,
        description="Wallet type (personal, merchant, agent...)",
        title="Account Type",
    )
    kyc_level: Optional[str] = Field(
        None, description="KYC verification level", title="KYC Level"
    )
    status: Optional[str] = Field(
        None, description="Wallet status (active, suspended...)", title="Status"
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_phone_number(cls, data: Any) -> Any:
        """Normalize the number to E.164, using country as the parsing region for
        local formats. Unparseable numbers are kept (cleaned) rather than rejected,
        so imports of messy statements don't drop transactions."""
        if isinstance(data, str):
            data = {"phone_number": data}
        if not isinstance(data, dict) or not data.get("phone_number"):
            return data

        raw = str(data["phone_number"]).strip()
        country = data.get("country")
        region = country.upper() if isinstance(country, str) else None
        try:
            parsed = phonenumbers.parse(raw, None if raw.startswith("+") else region)
            if phonenumbers.is_valid_number(parsed):
                data["phone_number"] = phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.E164
                )
                return data
        except NumberParseException:
            pass

        data["phone_number"] = "".join(c for c in raw if c.isdigit() or c == "+")
        return data

    @model_validator(mode="after")
    def compute_label(self) -> Self:
        self.nodeLabel = (
            f"{self.phone_number} ({self.provider})"
            if self.provider
            else self.phone_number
        )
        return self
