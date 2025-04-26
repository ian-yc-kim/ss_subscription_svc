import logging
import datetime

from sqlalchemy.orm import Session

# Import the Subscription model. Assumes it is defined in models/subscription.py
from ss_subscription_svc.models.subscription import Subscription


def process_event(event: dict, db: Session) -> None:
    """
    Process a Stripe event and update subscription records accordingly.

    :param event: Dictionary representing the Stripe event payload.
    :param db: SQLAlchemy Session instance.
    :raises Exception: on any processing or commit failures.
    """
    try:
        event_type = event.get('type')
        if not event_type:
            error_msg = "Missing 'type' in event payload"
            logging.error(error_msg)
            raise ValueError(error_msg)

        event_id = event.get('id', 'N/A')
        timestamp = event.get('created', datetime.datetime.utcnow().timestamp())

        if event_type == 'invoice.payment_succeeded':
            # Extract subscription id from event data, assumed to be under data.object.subscription
            sub_id = event.get('data', {}).get('object', {}).get('subscription')
            if not sub_id:
                error_msg = "Missing subscription id in invoice.payment_succeeded event"
                logging.error(error_msg)
                raise ValueError(error_msg)

            subscription = db.query(Subscription).filter(Subscription.stripe_subscription_id == sub_id).first()
            if subscription:
                subscription.status = 'active'
                db.add(subscription)
                try:
                    db.commit()
                    logging.info(f"Event {event_id} at {timestamp}: invoice.payment_succeeded processed successfully. Subscription {sub_id} set to active.")
                except Exception as commit_error:
                    db.rollback()
                    logging.error(commit_error, exc_info=True)
                    raise commit_error
            else:
                logging.info(f"Event {event_id}: Subscription with id {sub_id} not found during invoice.payment_succeeded processing.")

        elif event_type == 'customer.subscription.deleted':
            # Extract subscription id from event data
            sub_id = event.get('data', {}).get('object', {}).get('subscription')
            if not sub_id:
                error_msg = "Missing subscription id in customer.subscription.deleted event"
                logging.error(error_msg)
                raise ValueError(error_msg)

            subscription = db.query(Subscription).filter(Subscription.stripe_subscription_id == sub_id).first()
            if subscription:
                subscription.status = 'cancelled'
                db.add(subscription)
                try:
                    db.commit()
                    logging.info(f"Event {event_id} at {timestamp}: customer.subscription.deleted processed successfully. Subscription {sub_id} set to cancelled.")
                except Exception as commit_error:
                    db.rollback()
                    logging.error(commit_error, exc_info=True)
                    raise commit_error
            else:
                logging.info(f"Event {event_id}: Subscription with id {sub_id} not found during customer.subscription.deleted processing.")

        else:
            logging.info(f"Unhandled event type: {event_type} for event {event_id} at {timestamp}. No action taken.")

    except Exception as e:
        logging.error(e, exc_info=True)
        raise
