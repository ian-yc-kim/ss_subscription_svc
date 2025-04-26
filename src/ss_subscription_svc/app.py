from fastapi import FastAPI
from ss_subscription_svc.routers import stripe_router

app = FastAPI(debug=True)

# Include the Stripe router under the '/api/stripe' prefix
app.include_router(stripe_router.router, prefix="/api/stripe")
