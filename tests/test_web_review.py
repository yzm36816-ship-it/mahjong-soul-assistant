from fastapi.testclient import TestClient

from mahjong_assistant.application.events import GameEvent
from mahjong_assistant.infrastructure.storage import History
from mahjong_assistant.web.api import create_app


def test_dashboard_exposes_grounded_demo_without_private_assets(tmp_path):
    app = create_app(History(tmp_path / "history.sqlite3"), tmp_path / "models", tmp_path / "empty-site")
    client = TestClient(app)
    assert client.get("/api/health").json()["local_only"]
    sessions = client.get("/api/sessions").json()
    assert {item["id"] for item in sessions} == {"demo-3p", "demo-4p"}
    events = client.get("/api/sessions/demo-3p/events").json()
    assert events[-1]["kind"] == "tracking_gap"
    reply = client.post("/api/review", json={"session_id": "demo-3p", "question": "上家听牌了吗？"}).json()
    assert "不足以确认" in reply["answer"]
    assert reply["evidence"]
    assert client.get("/api/metrics").json()["3"]["promoted"] is False
    assert client.post("/api/corrections", json={"session_id": "demo-3p", "sequence": 2,
                                                  "field": "tile", "corrected_value": "2p"}).status_code == 400


def test_private_correction_does_not_rewrite_observed_event(tmp_path):
    history = History(tmp_path / "history.sqlite3")
    event = GameEvent("real-1", 1, 1, "discard", "top", "9s", "test", "2026-01-01T00:00:00Z", "observed")
    history.record_events([event])
    client = TestClient(create_app(history, tmp_path / "models", tmp_path / "empty-site"))
    response = client.post("/api/corrections", json={"session_id": "real-1", "sequence": 1,
                                                     "field": "tile", "corrected_value": "8s"})
    assert response.status_code == 200
    assert response.json()["automatically_trained"] is False
    assert history.events("real-1")[0]["tile"] == "9s"
    assert history.corrections("real-1")[0]["corrected_value"] == "8s"
