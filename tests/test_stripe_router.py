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
    # Override process_webhook_event to return a predefined event
    def fake_process_webhook_event(self, payload, sig_header, endpoint_secret):
        return {
            "id": "evt_test",
            "type": "invoice.payment_succeeded",
            "data": {"object": {"subscription": "sub_123"}},
            "created": 1234567890
        }
    monkeypatch.setattr(StripeIntegration, "process_webhook_event", fake_process_webhook_event)
    # Also override process_event to do nothing (simulate successful processing)
    # Correct the module path for process_event
    monkeypatch.setattr('ss_subscription_svc.routers.stripe_router.process_event', lambda event, db: None)

    os.environ["STRIPE_ENDPOINT_SECRET"] = "secret_test"
    headers = {"Stripe-Signature": "test_signature"}
    payload = '{"test": "data"}'
    response = client.post("/api/stripe/webhook", data=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["event"]["id"] == "evt_test"
    # Check that metadata is constructed properly
    expected_metadata = {"subscription_id": "sub_123", "status": "active"}
    assert data["metadata"] == expected_metadata


def test_process_webhook_missing_signature(client):
    payload = '{"test": "data"}'
    response = client.post("/api/stripe/webhook", data=payload)
    assert response.status_code == 400
    data = response.json()
    assert "Missing Stripe-Signature header" in data["detail"]


def test_process_webhook_processor_failure(client, monkeypatch):
    # Simulate a failure in process_event
    def fake_process_webhook_event(self, payload, sig_header, endpoint_secret):
        return {
            "id": "evt_fail",
            "type": "invoice.payment_succeeded",
            "data": {"object": {"subscription": "sub_fail"}},
            "created": 1234567890
        }
    monkeypatch.setattr(StripeIntegration, "process_webhook_event", fake_process_webhook_event)
    # Override process_event to raise an exception; correct the module path
    monkeypatch.setattr('ss_subscription_svc.routers.stripe_router.process_event', lambda event, db: (_ for _ in ()).throw(Exception("Processor error")))

    os.environ["STRIPE_ENDPOINT_SECRET"] = "secret_test"
    headers = {"Stripe-Signature": "test_signature"}
    payload = '{"test": "data"}'
    response = client.post("/api/stripe/webhook", data=payload, headers=headers)
    assert response.status_code == 400
    data = response.json()
    assert "Error processing webhook event" in data["detail"]


def test_get_subscription_success(client, monkeypatch):
    def fake_retrieve_subscription(self, subscription_id):
        return {"id": subscription_id, "status": "active"}
    monkeypatch.setattr(StripeIntegration, "retrieve_subscription", fake_retrieve_subscription)
    response = client.get("/api/stripe/subscription/sub_test")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["subscription"]["id"] == "sub_test"


def test_get_subscription_failure(client, monkeypatch):
    def fake_retrieve_subscription(self, subscription_id):
        raise ValueError("subscription_id cannot be empty")
    monkeypatch.setattr(StripeIntegration, "retrieve_subscription", fake_retrieve_subscription)
    response = client.get("/api/stripe/subscription/   ")
    assert response.status_code == 400
    data = response.json()
    assert "subscription_id cannot be empty" in data["detail"]


def test_update_subscription_success(client, monkeypatch):
    def fake_update_subscription(self, subscription_id, update_data):
        return {"id": subscription_id, "metadata": update_data.get("metadata", {})}
    monkeypatch.setattr(StripeIntegration, "update_subscription", fake_update_subscription)
    payload = {"metadata": {"key": "value"}}
    response = client.put("/api/stripe/subscription/sub_test", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["subscription"]["metadata"] == {"key": "value"}


def test_update_subscription_failure(client, monkeypatch):
    def fake_update_subscription(self, subscription_id, update_data):
        raise ValueError("Invalid update data")
    monkeypatch.setattr(StripeIntegration, "update_subscription", fake_update_subscription)
    payload = {"metadata": {"key": "value"}}
    response = client.put("/api/stripe/subscription/sub_test", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert "Invalid update data" in data["detail"]


def test_delete_subscription_success(client, monkeypatch):
    def fake_cancel_subscription(self, subscription_id):
        return {"id": subscription_id, "status": "canceled"}
    monkeypatch.setattr(StripeIntegration, "cancel_subscription", fake_cancel_subscription)
    response = client.delete("/api/stripe/subscription/sub_test")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["subscription"]["status"] == "canceled"


def test_delete_subscription_failure(client, monkeypatch):
    def fake_cancel_subscription(self, subscription_id):
        raise ValueError("Cancellation failed")
    monkeypatch.setattr(StripeIntegration, "cancel_subscription", fake_cancel_subscription)
    response = client.delete("/api/stripe/subscription/sub_test")
    assert response.status_code == 400
    data = response.json()
    assert "Cancellation failed" in data["detail"]
