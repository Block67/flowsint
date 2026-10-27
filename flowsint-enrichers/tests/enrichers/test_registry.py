import pytest

from flowsint_enrichers import ENRICHER_REGISTRY


def test_enricher_registry_enricher_found():
    enricher = ENRICHER_REGISTRY.get_enricher(
        "cryptowallet_to_transactions", "123", "123"
    )
    assert enricher.name() == "cryptowallet_to_transactions"


def test_enricher_registry_enricher_not_found():
    with pytest.raises(Exception) as error:
        ENRICHER_REGISTRY.get_enricher("enricher_does_not_exist", "123", "123")
        assert "not found" in str(error.value)
