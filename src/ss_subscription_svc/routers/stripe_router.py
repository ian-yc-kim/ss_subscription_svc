import os
import logging

from fastapi import APIRouter, HTTPException, Request, status, Depends
from pydantic import BaseModel

from ss_subscription_svc.stripe_integration import StripeIntegration
from ss_subscription_svc.models.base import get_db
from ss_subscription_svc.stripe_event_processor import process_event

router = APIRouter()

class SubscriptionRequest(BaseModel):
    customer_id: str
    price_id: str

@router.post("/subscription", status_code=201)
async def create_subscription(subscription_request: SubscriptionRequest):
    stripe_integration = StripeIntegration()
    try:
        subscription = stripe_integration.create_subscription(subscription_request.customer_id, subscription_request.price_id)
        return {"success": True, "subscription": subscription}
    except Exception as e:
        logging.error(e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/webhook", status_code=200)
async def process_webhook(request: Request, db = Depends(get_db)):
    payload_bytes = await request.body()
    payload = payload_bytes.decode('utf-8')
    sig_header = request.headers.get("Stripe-Signature")
    if not sig_header:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Stripe-Signature header")
    endpoint_secret = os.getenv("STRIPE_ENDPOINT_SECRET")
    if not endpoint_secret:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Stripe endpoint secret not configured")
    stripe_integration = StripeIntegration()
    try:
        event = stripe_integration.process_webhook_event(payload, sig_header, endpoint_secret)
    except Exception as e:
        logging.error(e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    try:
        # Process the event using the new event processor
        process_event(event, db)
        # Build metadata based on event type
        event_type = event.get('type', '')
        if event_type == 'invoice.payment_succeeded':
            sub_id = event.get('data', {}).get('object', {}).get('subscription')
            metadata = {"subscription_id": sub_id, "status": "active"}
        elif event_type == 'customer.subscription.deleted':
            sub_id = event.get('data', {}).get('object', {}).get('subscription')
            metadata = {"subscription_id": sub_id, "status": "cancelled"}
        else:
            metadata = {}
    except Exception as e:
        logging.error(e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Error processing webhook event")

    return {"success": True, "event": event, "metadata": metadata}

# New endpoints for subscription lifecycle operations

class SubscriptionUpdateRequest(BaseModel):
    # Accepts arbitrary update data, for example metadata updates
    metadata: dict

@router.get("/subscription/{subscription_id}", status_code=200)
async def get_subscription(subscription_id: str):
    stripe_integration = StripeIntegration()
    try:
        subscription = stripe_integration.retrieve_subscription(subscription_id)
        return {"success": True, "subscription": subscription}
    except ValueError as ve:
        logging.error(ve, exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logging.error(e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/subscription/{subscription_id}", status_code=200)
async def update_subscription(subscription_id: str, update_request: SubscriptionUpdateRequest):
    stripe_integration = StripeIntegration()
    try:
        # Use the update data from the request
        updated_subscription = stripe_integration.update_subscription(subscription_id, update_request.dict(exclude_unset=True))
        return {"success": True, "subscription": updated_subscription}
    except ValueError as ve:
        logging.error(ve, exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logging.error(e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/subscription/{subscription_id}", status_code=200)
async def cancel_subscription(subscription_id: str):
    stripe_integration = StripeIntegration()
    try:
        canceled_subscription = stripe_integration.cancel_subscription(subscription_id)
        return {"success": True, "subscription": canceled_subscription}
    except ValueError as ve:
        logging.error(ve, exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logging.error(e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
