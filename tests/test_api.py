import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
PAYLOAD = json.loads((ROOT / "samples" / "request.json").read_text())
KEY = "test-key"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("API_KEY", KEY)
    from app.main import app

    return TestClient(app)


def test_rejects_missing_key(client: TestClient) -> None:
    assert client.post("/predict", json=PAYLOAD).status_code == 401


def test_rejects_wrong_key(client: TestClient) -> None:
    assert client.post("/predict", json=PAYLOAD, headers={"x-api-key": "nope"}).status_code == 401


def test_predict_default(client: TestClient) -> None:
    res = client.post("/predict", json=PAYLOAD, headers={"x-api-key": KEY})
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"model_name", "model_version", "fraud_score", "is_fraud", "threshold"}
    assert body["model_name"] == "fraud-lgbm"
    assert len(body["model_version"]) == 12
    assert body["is_fraud"] is True


def test_threshold_and_fields_adjust_response(client: TestClient) -> None:
    res = client.post("/predict?threshold=0.99&fields=is_fraud", json=PAYLOAD, headers={"x-api-key": KEY})
    assert res.json() == {"is_fraud": False}


def test_optional_fields_default_to_missing(client: TestClient) -> None:
    optional = {"prev_address_months_count", "current_address_months_count", "bank_months_count",
                "session_length_in_minutes", "device_distinct_emails_8w"}
    payload = {k: v for k, v in PAYLOAD.items() if k not in optional}
    assert client.post("/predict", json=payload, headers={"x-api-key": KEY}).status_code == 200


def test_mandatory_field_missing_returns_422(client: TestClient) -> None:
    payload = {k: v for k, v in PAYLOAD.items() if k != "income"}
    assert client.post("/predict", json=payload, headers={"x-api-key": KEY}).status_code == 422
