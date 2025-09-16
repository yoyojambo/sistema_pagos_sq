
from fastapi.testclient import TestClient
import sys, os

ROOT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(ROOT, ".."))
if ROOT not in sys.path:
    sys.path.append(ROOT)

import app  # uses the FastAPI app and decision_engine

client = TestClient(app.app)

def test_health_endpoint():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_config_endpoint():
    r = client.get("/config")
    assert r.status_code == 200
    assert isinstance(r.json(), dict)
    assert "score_to_decision" in r.json()

def test_transaction_endpoint():
    payload = {
        "transaction_id": 42,
        "amount_mxn": 5200.0,
        "customer_txn_30d": 1,
        "geo_state": "Nuevo León",
        "device_type": "mobile",
        "chargeback_count": 0,
        "hour": 23,
        "product_type": "digital",
        "latency_ms": 180,
        "user_reputation": "new",
        "device_fingerprint_risk": "low",
        "ip_risk": "medium",
        "email_risk": "new_domain",
        "bin_country": "MX",
        "ip_country": "MX"
    }
    r = client.post("/transaction", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["transaction_id"] == 42
    assert body["decision"] in ("ACCEPTED", "IN_REVIEW", "REJECTED")
    assert isinstance(body["risk_score"], int)
