import os
os.environ['STRIPE_API_KEY'] = 'sk_test_dummy'

import time
import stripe
import logging
import pytest

from ss_subscription_svc.stripe_integration import StripeIntegration


class DummyStripeError(Exception):
    pass


class FakeStripe:
    """A fake stripe module to simulate API calls."""

    def __init__(self):
        self.call_count = 0

    def create_subscription(self, customer, items):
        self.call_count += 1
        # Simulate failure for first two calls
        if self.call_count < 3:
            raise stripe.error.APIConnectionError('Simulated connection error')
        return {"id": "sub_123", "customer": customer, "items": items}

    def modify(self, subscription_id, **update_data):
        self.call_count += 1
        # Simulate authentication error for the first call
        if self.call_count < 2:
            raise stripe.error.AuthenticationError('Simulated authentication error')
        updated = {"id": subscription_id}
        updated.update(update_data)
        return updated

    def delete(self, subscription_id):
        self.call_count += 1
        # Simulate success immediately
        return {"id": subscription_id, "status": "canceled"}

    def construct_event(self, payload, sig_header, endpoint_secret):
        if sig_header != 'valid_signature':
            raise stripe.error.SignatureVerificationError('Invalid signature', sig_header)
        return {"id": "evt_123", "payload": payload}


@pytest.fixture
def stripe_integration(monkeypatch):
    # Create an instance of StripeIntegration with lower retry settings for tests
    si = StripeIntegration(max_retries=3, retry_delay=0.1)
    return si


def test_create_subscription_success(monkeypatch, stripe_integration):
    fake_stripe = FakeStripe()

    # Monkey-patch stripe.Subscription.create to use our fake implementation
    monkeypatch.setattr(stripe, 'Subscription', type('FakeSubscription', (), {'create': fake_stripe.create_subscription}))

    result = stripe_integration.create_subscription(customer_id='cus_test', price_id='price_test')
    assert result["id"] == "sub_123"
    assert fake_stripe.call_count == 3


def test_update_subscription_success(monkeypatch, stripe_integration):
    fake_stripe = FakeStripe()
    # Reset call count for update simulation
    fake_stripe.call_count = 0
    monkeypatch.setattr(stripe, 'Subscription', type('FakeSubscription', (), {'modify': fake_stripe.modify}))

    result = stripe_integration.update_subscription(subscription_id='sub_test', update_data={"metadata": {"key": "value"}})
    assert result["id"] == "sub_test"
    assert result["metadata"]["key"] == "value"
    # Expect one retry due to simulated error if call_count < 2
    assert fake_stripe.call_count >= 2


def test_cancel_subscription_success(monkeypatch, stripe_integration):
    fake_stripe = FakeStripe()
    fake_stripe.call_count = 0
    monkeypatch.setattr(stripe, 'Subscription', type('FakeSubscription', (), {'delete': fake_stripe.delete}))

    result = stripe_integration.cancel_subscription(subscription_id='sub_cancel')
    assert result["id"] == "sub_cancel"
    assert result["status"] == "canceled"


def test_process_webhook_event_success(monkeypatch, stripe_integration):
    fake_stripe = FakeStripe()
    monkeypatch.setattr(stripe, 'Webhook', type('FakeWebhook', (), {'construct_event': fake_stripe.construct_event}))

    payload = '{"data": "test"}'
    sig_header = 'valid_signature'
    endpoint_secret = 'secret'
    result = stripe_integration.process_webhook_event(payload, sig_header, endpoint_secret)
    assert result["id"] == "evt_123"
    assert result["payload"] == payload


def test_process_webhook_event_invalid_signature(monkeypatch, stripe_integration):
    fake_stripe = FakeStripe()
    monkeypatch.setattr(stripe, 'Webhook', type('FakeWebhook', (), {'construct_event': fake_stripe.construct_event}))

    payload = '{"data": "test"}'
    sig_header = 'invalid_signature'
    endpoint_secret = 'secret'
    with pytest.raises(Exception) as excinfo:
        stripe_integration.process_webhook_event(payload, sig_header, endpoint_secret)
    assert 'Invalid signature' in str(excinfo.value)
