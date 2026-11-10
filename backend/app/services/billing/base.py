from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class CheckoutResult:
    provider: str
    checkout_url: Optional[str] = None
    paid: bool = False  # mock provider settles immediately
    provider_payment_id: Optional[str] = None


class BillingProvider:
    name = "base"

    def create_request_checkout(
        self, *, request_id: int, client_id: int, customer_email: str, product_name: str,
        amount: float, currency: str, success_url: str, cancel_url: str,
    ) -> CheckoutResult:
        """One-time payment for a single design request."""
        raise NotImplementedError

    def verify_session(self, session_id: str) -> Dict[str, Any]:
        """Check a checkout session directly (used when the client returns from checkout, no webhook needed).
        Returns {paid: bool, request_id, amount, currency, payment_id}."""
        return {"paid": False}

    def handle_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        """Returns a normalised event dict: {type, request_id, amount, currency, payment_id, ...}."""
        raise NotImplementedError

    def payment_details(self, payment_id: str) -> Dict[str, Any]:
        """How a settled payment was made (method, card, receipt, fees). Empty when the provider cannot say."""
        return {}
