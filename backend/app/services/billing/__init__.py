from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import settings
from app.services.billing.base import BillingProvider, CheckoutResult  # noqa: F401
from app.services.billing.mock_provider import MockBilling  # noqa: F401
from app.services.billing.mock_provider import MockBilling

log = logging.getLogger("billing")


@lru_cache
def get_billing() -> BillingProvider:
    if settings.billing_provider.lower() == "stripe":
        try:
            from app.services.billing.stripe_provider import StripeBilling

            return StripeBilling()
        except Exception as exc:
            log.warning("Stripe unavailable (%s); using mock billing", exc)
    return MockBilling()
