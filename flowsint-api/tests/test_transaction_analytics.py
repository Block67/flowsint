"""Contract for the transaction analytics endpoints."""

import uuid
from unittest.mock import MagicMock

import pytest

from app.api.routes import transaction_analytics as analytics_route
from flowsint_core.core.auth import create_access_token
from flowsint_core.core.models import (
    Investigation,
    InvestigationUserRole,
    Profile,
    Sketch,
)
from flowsint_core.core.types import Role

T0 = 1_700_000_000
RECORDS = [
    {"id": "r1", "source": "a", "target": "b", "amount": 1000, "epoch": T0},
    {"id": "r2", "source": "b", "target": "c", "amount": 900, "epoch": T0 + 60},
    {"id": "r3", "source": "c", "target": "a", "amount": 800, "epoch": T0 + 120},
]


@pytest.fixture
def graph(monkeypatch):
    graph = MagicMock()
    graph.query.return_value = RECORDS
    monkeypatch.setattr(analytics_route, "create_graph_service", lambda **kw: graph)
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


def test_alerts_for_a_viewer(client, db_session, graph):
    headers, sketch_id = _seed_user(db_session, (Role.VIEWER,))

    res = client.post(
        f"/api/sketches/{sketch_id}/transactions/alerts",
        json={"detectors": ["cycle"]},
        headers=headers,
    )

    assert res.status_code == 200
    alerts = res.json()
    assert [a["type"] for a in alerts] == ["cycle"]
    assert alerts[0]["edge_ids"] == ["r1", "r2", "r3"]
    assert alerts[0]["details"]["return_ratio"] == 0.8


def test_alerts_with_params(client, db_session, graph):
    headers, sketch_id = _seed_user(db_session, (Role.OWNER,))

    res = client.post(
        f"/api/sketches/{sketch_id}/transactions/alerts",
        json={"detectors": ["cycle"], "params": {"cycle_max_length": 2}},
        headers=headers,
    )

    assert res.status_code == 200
    assert res.json() == []


def test_unknown_detector(client, db_session, graph):
    headers, sketch_id = _seed_user(db_session, (Role.OWNER,))

    res = client.post(
        f"/api/sketches/{sketch_id}/transactions/alerts",
        json={"detectors": ["nope"]},
        headers=headers,
    )

    assert res.status_code == 400


def test_trace(client, db_session, graph):
    headers, sketch_id = _seed_user(db_session, (Role.OWNER,))

    res = client.post(
        f"/api/sketches/{sketch_id}/transactions/trace",
        json={"node_id": "a", "max_hops": 2},
        headers=headers,
    )

    assert res.status_code == 200
    body = res.json()
    assert set(body["nodes"]) == {"a", "b", "c"}
    assert body["edge_ids"] == ["r1", "r2"]


def test_trace_rejects_too_many_hops(client, db_session, graph):
    headers, sketch_id = _seed_user(db_session, (Role.OWNER,))

    res = client.post(
        f"/api/sketches/{sketch_id}/transactions/trace",
        json={"node_id": "a", "max_hops": 50},
        headers=headers,
    )

    assert res.status_code == 422


def test_accounts_summary(client, db_session, graph):
    headers, sketch_id = _seed_user(db_session, (Role.OWNER,))

    res = client.get(
        f"/api/sketches/{sketch_id}/transactions/accounts?limit=1", headers=headers
    )

    assert res.status_code == 200
    (top,) = res.json()
    # b moved 1000 in + 900 out, the largest volume
    assert top["node_id"] == "b"
    assert top["net"] == 100


def test_forbidden_without_role(client, db_session, graph):
    headers, _ = _seed_user(db_session, (Role.OWNER,))
    _, other_sketch = _seed_user(db_session, (Role.OWNER,))

    res = client.get(
        f"/api/sketches/{other_sketch}/transactions/accounts", headers=headers
    )

    assert res.status_code == 403
    graph.query.assert_not_called()


def test_unknown_sketch(client, db_session, graph):
    headers, _ = _seed_user(db_session, (Role.OWNER,))

    res = client.get(
        f"/api/sketches/{uuid.uuid4()}/transactions/accounts", headers=headers
    )

    assert res.status_code == 404
