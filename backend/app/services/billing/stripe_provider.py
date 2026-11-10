"""Stripe Checkout (one-time payment per request) + webhook.

Setup: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, BILLING_PROVIDER=stripe.
Webhook endpoint: POST {APP_URL}/api/v1/billing/webhook  (event: checkout.session.completed)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict

from app.core.config import settings
from app.services.billing.base import BillingProvider, CheckoutResult

ZERO_DECIMAL = {"JPY", "KRW"}


def _plain(obj: Any) -> Dict[str, Any]:
    """StripeObject -> plain dict (works across stripe-python versions)."""
    if isinstance(obj, dict) and not hasattr(obj, "to_dict"):
        return obj
    for attr in ("to_dict_recursive", "to_dict"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                return fn()
            except TypeError:
                continue
    return json.loads(str(obj))


class StripeBilling(BillingProvider):
    name = "stripe"

    def __init__(self) -> None:
        import stripe

        if not settings.stripe_secret_key:
            raise RuntimeError("STRIPE_SECRET_KEY not set")
        stripe.api_key = settings.stripe_secret_key
        self.stripe = stripe

    def create_request_checkout(self, *, request_id: int, client_id: int, customer_email: str, product_name: str,
                                amount: float, currency: str, success_url: str, cancel_url: str) -> CheckoutResult:
        cur = currency.lower()
        unit = int(round(amount)) if currency.upper() in ZERO_DECIMAL else int(round(amount * 100))
        session = self.stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price_data": {"currency": cur, "unit_amount": unit, "product_data": {"name": product_name[:120]}}, "quantity": 1}],
            success_url=success_url + ("&" if "?" in success_url else "?") + "session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            customer_email=customer_email,
            client_reference_id=str(request_id),
            metadata={"request_id": str(request_id), "client_id": str(client_id)},
        )
        return CheckoutResult(provider=self.name, checkout_url=session.url, paid=False)

    def verify_session(self, session_id: str) -> Dict[str, Any]:
        sess = self.stripe.checkout.Session.retrieve(session_id)
        cur = (sess.get("currency") or settings.currency).upper()
        total = sess.get("amount_total") or 0
        return {
            "paid": sess.get("payment_status") == "paid",
            "request_id": int((sess.get("metadata") or {}).get("request_id") or sess.get("client_reference_id") or 0),
            "amount": total if cur in ZERO_DECIMAL else total / 100,
            "currency": cur,
            "payment_id": sess.get("payment_intent") or sess.get("id"),
        }

    def payment_details(self, payment_id: str) -> Dict[str, Any]:
        """Method, card, receipt and settlement of a payment (PaymentIntent id, or a Checkout Session id)."""
        pid = payment_id
        if pid.startswith("cs_"):
            pid = _plain(self.stripe.checkout.Session.retrieve(pid)).get("payment_intent") or ""
        pi = _plain(self.stripe.PaymentIntent.retrieve(pid, expand=["latest_charge.balance_transaction", "payment_method"]))
        charge = pi.get("latest_charge") if isinstance(pi.get("latest_charge"), dict) else {}
        pmd = charge.get("payment_method_details") or {}
        pm = pi.get("payment_method") if isinstance(pi.get("payment_method"), dict) else {}
        card = pmd.get("card") or pm.get("card") or {}
        mtype = pmd.get("type") or pm.get("type")
        raw = pmd.get(mtype) if mtype and mtype != "card" and isinstance(pmd.get(mtype), dict) else {}
        extra: Dict[str, Any] = {}
        for k, v in raw.items():  # wallet / bank specifics, e.g. Revolut Pay transaction_id, PayPal payer_email
            if isinstance(v, dict):
                extra.update({f"{k}_{kk}": vv for kk, vv in v.items() if vv not in (None, "") and not isinstance(vv, (dict, list))})
            elif v not in (None, "") and not isinstance(v, list):
                extra[k] = v
        funding_card = (raw.get("funding") or {}).get("card") if isinstance(raw.get("funding"), dict) else None
        if not card and isinstance(funding_card, dict):
            card = funding_card
        bt = charge.get("balance_transaction") if isinstance(charge.get("balance_transaction"), dict) else {}
        billing = charge.get("billing_details") or pm.get("billing_details") or {}
        outcome = charge.get("outcome") or {}
        cur = (pi.get("currency") or "").upper()
        live = bool(pi.get("livemode"))

        def money(v: Any, c: str = cur) -> Any:
            return None if v is None else (v if c in ZERO_DECIMAL else round(v / 100, 2))

        def when(ts: Any) -> Any:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat() if ts else None

        return {
            "source": "stripe",
            "livemode": live,
            "payment_intent_id": pi.get("id"),
            "charge_id": charge.get("id"),
            "status": pi.get("status"),
            "method_type": mtype,
            "method_details": extra,
            "card": {
                "brand": card.get("brand"), "last4": card.get("last4"), "exp_month": card.get("exp_month"), "exp_year": card.get("exp_year"),
                "funding": card.get("funding"), "country": card.get("country"), "network": card.get("network"),
                "wallet": (card.get("wallet") or {}).get("type"), "three_d_secure": (card.get("three_d_secure") or {}).get("result"),
            } if card else None,
            "billing_name": billing.get("name"),
            "billing_email": billing.get("email") or pi.get("receipt_email"),
            "billing_country": (billing.get("address") or {}).get("country"),
            "amount": money(pi.get("amount_received") or pi.get("amount")),
            "currency": cur,
            "created": when(pi.get("created")),
            "receipt_url": charge.get("receipt_url"),
            "receipt_number": charge.get("receipt_number"),
            "risk_level": outcome.get("risk_level"),
            "network_status": outcome.get("network_status"),
            "seller_message": outcome.get("seller_message"),
            "fee": money(bt.get("fee"), (bt.get("currency") or cur).upper()) if bt else None,
            "net": money(bt.get("net"), (bt.get("currency") or cur).upper()) if bt else None,
            "settlement_currency": (bt.get("currency") or "").upper() or None,
            "available_on": when(bt.get("available_on")) if bt else None,
            "dashboard_url": f"https://dashboard.stripe.com/{'' if live else 'test/'}payments/{pi.get('id')}",
        }

    def handle_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        event = self.stripe.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)
        obj = event["data"]["object"]
        etype = event["type"]
        out: Dict[str, Any] = {"type": etype, "raw_id": event["id"]}
        if etype == "checkout.session.completed":
            cur = (obj.get("currency") or settings.currency).upper()
            total = obj.get("amount_total") or 0
            out.update({
                "request_id": int((obj.get("metadata") or {}).get("request_id") or obj.get("client_reference_id") or 0),
                "amount": total if cur in ZERO_DECIMAL else total / 100,
                "currency": cur,
                "payment_id": obj.get("payment_intent") or obj.get("id"),
                "invoice_url": obj.get("url"),
            })
        return out
