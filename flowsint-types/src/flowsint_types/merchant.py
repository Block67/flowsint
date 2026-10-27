from typing import Optional, Self

from pydantic import Field, model_validator

from .flowsint_base import FlowsintType
from .registry import flowsint_type


@flowsint_type
class Merchant(FlowsintType):
    """Represents a merchant / payment acceptor receiving transactions."""

    name: str = Field(
        ...,
        description="Merchant name as it appears on statements",
        title="Name",
        json_schema_extra={"primary": True},
    )
    merchant_id: Optional[str] = Field(
        None,
        description="Merchant identifier at the acquirer or provider",
        title="Merchant ID",
    )
    category: Optional[str] = Field(
        None, description="Business category", title="Category"
    )
    mcc: Optional[str] = Field(
        None, description="Merchant Category Code (ISO 18245)", title="MCC"
    )
    country: Optional[str] = Field(
        None, description="Country code (ISO 3166-1 alpha-2)", title="Country Code"
    )
    provider: Optional[str] = Field(
        None,
        description="Acquirer or payment provider the merchant uses",
        title="Provider",
    )

    @model_validator(mode="after")
    def compute_label(self) -> Self:
        self.nodeLabel = (
            f"{self.name} [{self.merchant_id}]" if self.merchant_id else self.name
        )
        return self
