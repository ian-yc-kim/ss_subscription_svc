from sqlalchemy import Column, String
from ss_subscription_svc.models.base import Base


class Subscription(Base):
    """
    Subscription model representing a Stripe subscription record.
    """
    __tablename__ = 'subscriptions'

    stripe_subscription_id = Column(String, primary_key=True, unique=True, nullable=False)
    status = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<Subscription(id={self.stripe_subscription_id}, status={self.status})>"
