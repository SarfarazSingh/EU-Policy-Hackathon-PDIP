import sys
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app

client = TestClient(app)


def test_create_item_returns_pending() -> None:
    response = client.post("/api/items", json={"text": "Test disinfo claim", "type": "text"})
    assert response.status_code == 200
    data = response.json()
    assert "itemId" in data
    assert data["status"] == "pending"


def test_get_items_list() -> None:
    response = client.get("/api/items")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_item_escalate_and_delete_flow() -> None:
    created = client.post("/api/items", json={"text": "Flow test", "type": "text"})
    assert created.status_code == 200
    item_id = created.json()["itemId"]

    stop_resp = client.post(f"/api/items/{item_id}/stop")
    assert stop_resp.status_code == 200
    assert stop_resp.json()["status"] == "stopped"

    escalate_resp = client.post(f"/api/items/{item_id}/escalate")
    assert escalate_resp.status_code == 200
    assert escalate_resp.json()["status"] == "escalated"

    delete_resp = client.delete(f"/api/items/{item_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["deleted"] is True

    not_found_resp = client.get(f"/api/items/{item_id}")
    assert not_found_resp.status_code == 404


def test_toolkit_incident_create_and_fetch() -> None:
    payload = {
        "whatHappened": "Synthetic audio clip falsely claims polling hours changed.",
        "spreadChannels": "Messaging app groups, short-form video platform",
        "targetedGroups": "First-time voters",
        "claimSummary": "Polling closes at noon in district X",
        "confidenceEvidence": "Election authority link + timestamped screenshots",
        "ownerDeadline": "Press lead by 14:00",
        "recommendedAction": "Targeted correction",
        "triageFlags": [
            "Is there immediate harm potential (public safety, election procedures, intimidation, fraud)?",
            "Do we have authoritative sources available now for a correction?",
        ],
        "notes": "Coordinate with election authority contact before statement.",
        "riskLikelihood": 4,
        "riskReach": 4,
        "riskUrgency": 5,
        "riskScore": 80,
        "riskBand": "Escalate Immediately",
    }

    create_resp = client.post("/api/toolkit/incidents", json=payload)
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert "incidentId" in created
    assert created["riskBand"] == "Escalate Immediately"

    list_resp = client.get("/api/toolkit/incidents")
    assert list_resp.status_code == 200
    listed = list_resp.json()
    assert isinstance(listed, list)
    assert any(entry["incidentId"] == created["incidentId"] for entry in listed)

    detail_resp = client.get(f"/api/toolkit/incidents/{created['incidentId']}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["whatHappened"] == payload["whatHappened"]
    assert detail["riskScore"] == payload["riskScore"]
