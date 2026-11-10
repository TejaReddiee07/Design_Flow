"""Mock billing: marks the request as paid instantly (use until Stripe keys are added)."""
from __future__ import annotations

import secrets
from typing import Any, Dict

from app.services.billing.base import BillingProvider, CheckoutResult


class MockBilling(BillingProvider):
    name = "mock"

    def create_request_checkout(self, *, request_id: int, client_id: int, customer_email: str, product_name: str,
                                amount: float, currency: str, success_url: str, cancel_url: str) -> CheckoutResult:
        return CheckoutResult(provider=self.name, checkout_url=None, paid=True, provider_payment_id=f"mock_pay_{request_id}_{secrets.token_hex(4)}")

    def verify_session(self, session_id: str) -> Dict[str, Any]:
        return {"paid": True}

    def handle_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        return {"type": "ignored"}
