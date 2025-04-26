import pytest
import logging

from ss_subscription_svc import stripe_event_processor
from ss_subscription_svc.models.subscription import Subscription


def create_subscription(db, subscription_id: str, status: str = 'pending') -> Subscription:
    subscription = Subscription(stripe_subscription_id=subscription_id, status=status)
    db.add(subscription)
    db.commit()
    return subscription


def test_invoice_payment_succeeded_event(db_session):
    subscription_id = 'sub_123'
    db = db_session
    # Create a subscription record with initial status 'pending'
    create_subscription(db, subscription_id, 'pending')

    event = {
        "id": "evt_1",
        "type": "invoice.payment_succeeded",
        "data": {
            "object": {
                "subscription": subscription_id
            }
        },
        "created": 1234567890
    }

    stripe_event_processor.process_event(event, db)

    updated = db.query(Subscription).filter(Subscription.stripe_subscription_id == subscription_id).first()
    assert updated is not None
    assert updated.status == 'active'


def test_customer_subscription_deleted_event(db_session):
    subscription_id = 'sub_456'
    db = db_session
    # Create a subscription record with initial status 'active'
    create_subscription(db, subscription_id, 'active')

    event = {
        "id": "evt_2",
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "subscription": subscription_id
            }
        },
        "created": 1234567890
    }

    stripe_event_processor.process_event(event, db)

    updated = db.query(Subscription).filter(Subscription.stripe_subscription_id == subscription_id).first()
    assert updated is not None
    assert updated.status == 'cancelled'


def test_event_missing_type(db_session):
    db = db_session
    event = {"id": "evt_3", "data": {"object": {}}}
    with pytest.raises(ValueError) as excinfo:
        stripe_event_processor.process_event(event, db)
    assert "Missing 'type'" in str(excinfo.value)


def test_unhandled_event_type(db_session, caplog):
    db = db_session
    event = {
        "id": "evt_4",
        "type": "unknown.event",
        "data": {"object": {}},
        "created": 1234567890
    }
    stripe_event_processor.process_event(event, db)
    assert any("Unhandled event type" in record.message for record in caplog.records)


def test_commit_failure_event(db_session, monkeypatch):
    subscription_id = 'sub_fail'
    db = db_session
    create_subscription(db, subscription_id, 'pending')

    event = {
        "id": "evt_5",
        "type": "invoice.payment_succeeded",
        "data": {
            "object": {
                "subscription": subscription_id
            }
        },
        "created": 1234567890
    }

    original_commit = db.commit

    def failing_commit():
        raise Exception("Commit failed")

    monkeypatch.setattr(db, "commit", failing_commit)
    with pytest.raises(Exception, match="Commit failed"):
        stripe_event_processor.process_event(event, db)

    # Restore original commit method for cleanliness
    monkeypatch.setattr(db, "commit", original_commit)
