import os
import time
import logging
from typing import Any, Dict

import stripe

# Configure logging
logging.basicConfig(level=logging.INFO)

# Retrieve Stripe API key from environment variables
STRIPE_API_KEY = os.getenv('STRIPE_API_KEY')
if not STRIPE_API_KEY:
    raise EnvironmentError('Stripe API key (STRIPE_API_KEY) not set in environment variables.')

# Initialize the Stripe client
stripe.api_key = STRIPE_API_KEY


class StripeIntegration:
    """
    This class encapsulates the integration with the Stripe API, including
    subscription creation, management, and webhook event processing with
    robust error handling and a retry mechanism.
    """

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0) -> None:
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def create_subscription(self, customer_id: str, price_id: str) -> Dict[str, Any]:
        """
        Create a subscription for a customer using Stripe API with retry mechanism.

        :param customer_id: The ID of the customer in Stripe.
        :param price_id: The price ID for the subscription plan.
        :return: The created subscription as a dictionary.
        :raises Exception: if subscription creation fails after retries.
        """
        attempt = 0
        while attempt < self.max_retries:
            try:
                subscription = stripe.Subscription.create(
                    customer=customer_id,
                    items=[{'price': price_id}]
                )
                return subscription
            except (stripe.error.AuthenticationError, stripe.error.APIConnectionError) as e:
                logging.error(f"Error creating subscription (attempt {attempt + 1}): {e}", exc_info=True)
                attempt += 1
                time.sleep(self.retry_delay)
            except Exception as e:
                logging.error(f"General error during subscription creation: {e}", exc_info=True)
                raise e
        raise Exception('Failed to create subscription after retries.')

    def update_subscription(self, subscription_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing subscription using Stripe API with retry mechanism.

        :param subscription_id: The ID of the subscription to update.
        :param update_data: A dictionary of parameters to update.
        :return: The updated subscription as a dictionary.
        :raises Exception: if update fails after retries.
        """
        attempt = 0
        while attempt < self.max_retries:
            try:
                subscription = stripe.Subscription.modify(subscription_id, **update_data)
                return subscription
            except (stripe.error.AuthenticationError, stripe.error.APIConnectionError) as e:
                logging.error(f"Error updating subscription (attempt {attempt + 1}): {e}", exc_info=True)
                attempt += 1
                time.sleep(self.retry_delay)
            except Exception as e:
                logging.error(f"General error during subscription update: {e}", exc_info=True)
                raise e
        raise Exception('Failed to update subscription after retries.')

    def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Cancel an existing subscription using Stripe API with retry mechanism.

        :param subscription_id: The ID of the subscription to cancel.
        :return: The canceled subscription details as a dictionary.
        :raises Exception: if cancellation fails after retries.
        """
        attempt = 0
        while attempt < self.max_retries:
            try:
                canceled_subscription = stripe.Subscription.delete(subscription_id)
                return canceled_subscription
            except (stripe.error.AuthenticationError, stripe.error.APIConnectionError) as e:
                logging.error(f"Error canceling subscription (attempt {attempt + 1}): {e}", exc_info=True)
                attempt += 1
                time.sleep(self.retry_delay)
            except Exception as e:
                logging.error(f"General error during subscription cancellation: {e}", exc_info=True)
                raise e
        raise Exception('Failed to cancel subscription after retries.')

    def process_webhook_event(self, payload: str, sig_header: str, endpoint_secret: str) -> Dict[str, Any]:
        """
        Process and validate a webhook event from Stripe.

        :param payload: The raw payload from the webhook.
        :param sig_header: The Stripe-Signature header from the webhook.
        :param endpoint_secret: The webhook endpoint secret used for signature verification.
        :return: The reconstructed event from Stripe as a dictionary.
        :raises Exception: if signature verification or event processing fails.
        """
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
            return event
        except stripe.error.SignatureVerificationError as e:
            logging.error(f'Webhook signature verification failed: {e}', exc_info=True)
            raise Exception('Invalid signature.')
        except Exception as e:
            logging.error(f'General error processing webhook event: {e}', exc_info=True)
            raise e
