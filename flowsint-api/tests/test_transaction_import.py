"""Contract for the transaction statement import endpoints."""

import json
import uuid
from unittest.mock import MagicMock

import pytest

from app.api.routes import sketches as sketches_route
from flowsint_core.core.auth import create_access_token
from flowsint_core.core.models import (
    Investigation,
    InvestigationUserRole,
    Profile,
    Sketch,
)
from flowsint_core.core.types import Role

CSV = (
    "Référence;Date;Expéditeur;Destinataire;Montant\n"
    "OM001;02/01/2024;+221771234567;+221787654321;1 500\n"
    "OM002;03/01/2024;+221787654321;;200\n"
).encode()

MAPPING = {
    "mode": "ledger",
    "source": {"account_type": "MobileMoneyAccount", "column": "Expéditeur"},
    "target": {"account_type": "MobileMoneyAccount", "column": "Destinataire"},
    "transaction_id_column": "Référence",
    "date_column": "Date",
    "amount_column": "Montant",
    "currency": "XOF",
}


@pytest.fixture
def graph(monkeypatch):
    graph = MagicMock()
    monkeypatch.setattr(sketches_route, "create_graph_service", lambda **kwargs: graph)
    return graph


def _seed_user(db_session, roles):
    user = Profile(
        id=uuid.uuid4(), email=f"{uuid.uuid4()}@example.com", hashed_password="x"
    )
    investigation = Investigation(id=uuid.uuid4(), name="Case", owner_id=user.id)
    sketch = Sketch(
        id=uuid.uuid4(),
        title="Board",
        owner_id=user.id,
        investigation_id=investigation.id,
    )
    db_session.add_all([user, investigation, sketch])
    if roles:
        db_session.add(
            InvestigationUserRole(
                user_id=user.id, investigation_id=investigation.id, roles=list(roles)
            )
        )
    db_session.commit()
    headers = {"Authorization": f"Bearer {create_access_token({'sub': user.email})}"}
    return headers, str(sketch.id)


def _post(client, headers, sketch_id, step, mapping=None, filename="releve.csv"):
    data = {"mapping_json": json.dumps(mapping)} if mapping is not None else None
    return client.post(
        f"/api/sketches/{sketch_id}/import/transactions/{step}",
        files={"file": (filename, CSV, "text/csv")},
        data=data,
        headers=headers,
    )


def test_analyze_suggests_columns(client, db_session):
    headers, sketch_id = _seed_user(db_session, (Role.VIEWER,))

    res = _post(client, headers, sketch_id, "analyze")

    assert res.status_code == 200
    body = res.json()
    assert body["total_rows"] == 2
    assert body["suggested_mode"] == "ledger"
    assert body["suggested_columns"]["source"] == "Expéditeur"
    assert body["sample_rows"][0]["Montant"] == "1 500"


def test_analyze_rejects_unsupported_files(client, db_session):
    headers, sketch_id = _seed_user(db_session, (Role.OWNER,))

    res = _post(client, headers, sketch_id, "analyze", filename="notes.txt")

    assert res.status_code == 400


def test_preview_reports_row_errors(client, db_session):
    headers, sketch_id = _seed_user(db_session, (Role.OWNER,))

    res = _post(client, headers, sketch_id, "preview", MAPPING)

    assert res.status_code == 200
    body = res.json()
    assert body["valid_rows"] == 1
    assert body["errors"] == [
        {
            "row": 3,
            "message": "missing MobileMoneyAccount identifier in column 'Destinataire'",
        }
    ]
    assert body["sample"][0]["amount"] == 1500


def test_preview_rejects_invalid_mapping(client, db_session):
    headers, sketch_id = _seed_user(db_session, (Role.OWNER,))

    res = _post(client, headers, sketch_id, "preview", {"mode": "ledger"})

    assert res.status_code == 400
    assert "ledger mode needs a source and a target" in res.json()["detail"]


def test_execute_writes_transactions(client, db_session, graph):
    headers, sketch_id = _seed_user(db_session, (Role.EDITOR,))

    res = _post(client, headers, sketch_id, "execute", MAPPING)

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "completed_with_errors"
    assert body["transactions_imported"] == 1
    assert body["accounts_imported"] == 2
    assert graph.create_relationship.call_args.kwargs["edge_key"] == "OM001"


def test_execute_is_forbidden_for_a_viewer(client, db_session, graph):
    headers, sketch_id = _seed_user(db_session, (Role.VIEWER,))

    res = _post(client, headers, sketch_id, "execute", MAPPING)

    assert res.status_code == 403
    graph.create_relationship.assert_not_called()


def test_execute_rejects_unknown_sketch(client, db_session, graph):
    headers, _ = _seed_user(db_session, (Role.OWNER,))

    res = _post(client, headers, str(uuid.uuid4()), "execute", MAPPING)

    assert res.status_code == 404


def test_entity_import_is_forbidden_for_a_viewer(client, db_session, graph):
    headers, sketch_id = _seed_user(db_session, (Role.VIEWER,))

    res = client.post(
        f"/api/sketches/{sketch_id}/import/execute",
        data={"entity_mappings_json": json.dumps({"nodes": [], "edges": []})},
        headers=headers,
    )

    assert res.status_code == 403
