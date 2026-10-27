"""
Flowsint Types - Pydantic models for flowsint
"""

# Import registry first to ensure it's ready for auto-registration
# Import base class
# Auto-discover and register all types
# For backward compatibility, explicitly import commonly used types
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel

from .address import Location
from .affiliation import Affiliation
from .alias import Alias
from .bank_account import BankAccount
from .breach import Breach
from .credential import Credential
from .credit_card import CreditCard
from .device import Device
from .document import Document
from .domain import Domain
from .email import Email
from .file import File
from .flowsint_base import FlowsintType
from .individual import Individual
from .ip import Ip
from .leak import Leak
from .message import Message
from .organization import Organization
from .phone import Phone
from .phrase import Phrase
from .registry import TYPE_REGISTRY, flowsint_type, get_type, load_all_types
from .reputation_score import ReputationScore
from .risk_profile import RiskProfile
from .social_account import SocialAccount
from .username import Username
from .wallet import CryptoNFT, CryptoWallet, CryptoWalletTransaction
from .website import Website

load_all_types()

__version__ = "0.1.0"
__author__ = "dextmorgn <contact@flowsint.io>"

__all__ = [
    "Location",
    "Affiliation",
    "Alias",
    "BankAccount",
    "Breach",
    "Credential",
    "CreditCard",
    "Device",
    "Document",
    "Domain",
    "Email",
    "File",
    "Individual",
    "Ip",
    "Leak",
    "Message",
    "Organization",
    "Phone",
    "Phrase",
    "ReputationScore",
    "RiskProfile",
    "SocialAccount",
    "Username",
    "CryptoWallet",
    "CryptoWalletTransaction",
    "CryptoNFT",
    "Website",
    # Type registry utilities (legacy)
    "TYPE_TO_MODEL",
    "get_model_for_type",
    "serialize_pydantic_for_transport",
    "deserialize_pydantic_from_transport",
    # New type registry
    "TYPE_REGISTRY",
    "flowsint_type",
    "get_type",
    "FlowsintType",
]


# Type Registry: mapping Neo4j node types to Pydantic model classes
# Keys are lowercase to match Neo4j node type property
TYPE_TO_MODEL: Dict[str, Type[BaseModel]] = {
    "domain": Domain,
    "email": Email,
    "ip": Ip,
    "phone": Phone,
    "username": Username,
    "organization": Organization,
    "individual": Individual,
    "socialaccount": SocialAccount,
    "cryptowallet": CryptoWallet,
    "cryptowallettransaction": CryptoWalletTransaction,
    "cryptonft": CryptoNFT,
    "website": Website,
    "phrase": Phrase,
    "breach": Breach,
    "credential": Credential,
    "device": Device,
    "document": Document,
    "file": File,
    "location": Location,
    "affiliation": Affiliation,
    "alias": Alias,
    "bankaccount": BankAccount,
    "creditcard": CreditCard,
    "leak": Leak,
    "message": Message,
    "reputationscore": ReputationScore,
    "riskprofile": RiskProfile,
}


def get_model_for_type(type_name: str) -> Optional[Type[BaseModel]]:
    """
    Get the Pydantic model class for a given type name.

    Args:
        type_name: The type name as stored in Neo4j (case-insensitive)

    Returns:
        The corresponding Pydantic model class, or None if not found
    """
    return TYPE_TO_MODEL.get(type_name.lower())


reserved_properties = [
    "id",
    "x",
    "y",
    "nodeLabel",
    "label",
    "nodeType",
    "type",
    "nodeImage",
    "nodeIcon",
    "nodeColor",
    "nodeSize",
    "created_at",
    "sketch_id",
]


def serialize_pydantic_for_transport(obj: BaseModel) -> Dict[str, Any]:
    """
    Serialize a Pydantic object for transport (e.g., to Celery tasks).

    Args:
        obj: Pydantic model instance

    Returns:
        Dictionary representation suitable for JSON serialization
    """
    return obj.model_dump(mode="json")


def deserialize_pydantic_from_transport(
    data: Dict[str, Any], type_name: str
) -> Optional[BaseModel]:
    """
    Deserialize a dictionary back into a Pydantic model instance.

    Args:
        data: Dictionary representation of the object
        type_name: The type name (e.g., 'domain', 'ip')

    Returns:
        Pydantic model instance, or None if deserialization fails
    """
    model_class = get_model_for_type(type_name)

    if not model_class:
        return None

    try:
        return model_class(**data)
    except Exception:
        return None
