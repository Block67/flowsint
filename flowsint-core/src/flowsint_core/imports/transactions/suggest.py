"""
Guess which column holds which transaction field from header names (FR/EN).
"""

import re
import unicodedata
from typing import Dict, List, Optional

# Ordered: more specific fields first so e.g. "date valeur" isn't taken by amount.
FIELD_KEYWORDS: Dict[str, List[str]] = {
    "transaction_id": [
        "transaction id",
        "id transaction",
        "reference",
        "ref",
        "txid",
        "tx hash",
        "hash",
        "numero transaction",
        "n transaction",
        "id",
    ],
    "date": [
        "date operation",
        "date transaction",
        "date",
        "datetime",
        "timestamp",
        "horodatage",
        "time",
        "heure",
    ],
    "debit": ["debit", "retrait", "sortie", "withdrawal", "montant debit"],
    "credit": ["credit", "depot", "entree", "deposit", "montant credit"],
    "fees": ["frais", "fees", "fee", "commission"],
    "amount": ["montant", "amount", "valeur", "value", "somme"],
    "currency": ["devise", "currency", "monnaie", "ccy"],
    "source": [
        "expediteur",
        "emetteur",
        "sender",
        "from",
        "source",
        "payeur",
        "donneur d ordre",
        "numero expediteur",
    ],
    "target": [
        "destinataire",
        "beneficiaire",
        "receiver",
        "recipient",
        "beneficiary",
        "to",
        "target",
        "numero destinataire",
    ],
    "counterparty": ["contrepartie", "counterparty", "tiers", "correspondant"],
    "direction": ["sens", "direction", "type operation", "debit credit", "dr cr"],
    "description": [
        "libelle",
        "description",
        "motif",
        "narration",
        "memo",
        "details",
        "commentaire",
    ],
    "status": ["statut", "status", "etat"],
}


def normalize_header(header: str) -> str:
    text = unicodedata.normalize("NFKD", header).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return text.strip()


def suggest_columns(headers: List[str]) -> Dict[str, Optional[str]]:
    """Map each field to the best matching header (each header used once)."""
    normalized = {h: normalize_header(h) for h in headers}
    used: set = set()
    suggestion: Dict[str, Optional[str]] = {}

    for field_name, keywords in FIELD_KEYWORDS.items():
        match = _find(normalized, keywords, used, exact=True) or _find(
            normalized, keywords, used, exact=False
        )
        suggestion[field_name] = match
        if match:
            used.add(match)
    return suggestion


def _find(
    normalized: Dict[str, str], keywords: List[str], used: set, exact: bool
) -> Optional[str]:
    for keyword in keywords:
        for header, norm in normalized.items():
            if header in used:
                continue
            if exact and norm == keyword:
                return header
            if not exact and re.search(rf"\b{re.escape(keyword)}\b", norm):
                return header
    return None


def suggest_mode(suggestion: Dict[str, Optional[str]]) -> str:
    has_parties = suggestion.get("source") and suggestion.get("target")
    has_debit_credit = suggestion.get("debit") or suggestion.get("credit")
    if has_parties:
        return "ledger"
    if has_debit_credit or suggestion.get("counterparty"):
        return "statement"
    return "ledger"
