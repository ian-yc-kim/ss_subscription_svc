import os
import json
from ss_subscription_svc.stripe_integration import StripeIntegration

def test_create_subscription_success(client, monkeypatch):
    def fake_create_subscription(self, customer_id, price_id):
        return {"id": "sub_test", "customer": customer_id, "price": price_id}
    monkeypatch.setattr(StripeIntegration, "create_subscription", fake_create_subscription)
    payload = {"customer_id": "cust_test", "price_id": "price_test"}
    response = client.post("/api/stripe/subscription", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["subscription"]["id"] == "sub_test"


def test_process_webhook_success(client, monkeypatch):
    def fake_process_webhook_event(self, payload, sig_header, endpoint_secret):
        return {"id": "evt_test", "payload": payload}
    monkeypatch.setattr(StripeIntegration, "process_webhook_event", fake_process_webhook_event)
    os.environ["STRIPE_ENDPOINT_SECRET"] = "secret_test"
    headers = {"Stripe-Signature": "test_signature"}
    payload = '{"test": "data"}'
    response = client.post("/api/stripe/webhook", data=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["event"]["id"] == "evt_test"


def test_process_webhook_missing_signature(client):
    payload = '{"test": "data"}'
    response = client.post("/api/stripe/webhook", data=payload)
    assert response.status_code == 400
    data = response.json()
    assert "Missing Stripe-Signature header" in data["detail"]
