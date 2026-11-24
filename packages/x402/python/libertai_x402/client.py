from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import httpx
from eth_account import Account
from x402 import x402Client
from x402.client_base import PaymentPolicy, RequirementsView
from x402.http.clients.httpx import PaymentError, x402AsyncTransport
from x402.mechanisms.evm import EthAccountSigner
from x402.mechanisms.evm.exact import ExactEvmClientScheme
from x402.mechanisms.evm.upto import UptoEvmClientScheme

BASE_NETWORK = "eip155:8453"


class PaymentLimitError(PaymentError):
    """No payment option offered by the server fits the configured limits."""


def spending_policy(
    max_amount: int | None = None,
    allowed_pay_to: Iterable[str] | None = None,
) -> PaymentPolicy:
    """x402 policy keeping only requirements within ``max_amount`` (atomic units) and ``allowed_pay_to``."""
    allowed = None if allowed_pay_to is None else {a.lower() for a in allowed_pay_to}

    def policy(_version: int, reqs: list[RequirementsView]) -> list[RequirementsView]:
        kept = [
            r
            for r in reqs
            if (max_amount is None or int(r.get_amount()) <= max_amount)
            and (allowed is None or r.pay_to.lower() in allowed)
        ]
        if not kept:
            offered = ", ".join(f"{r.get_amount()} to {r.pay_to}" for r in reqs)
            raise PaymentLimitError(
                f"x402: no payment option within limits (max_amount={max_amount}, "
                f"allowed_pay_to={sorted(allowed) if allowed is not None else 'any'}); offered: {offered}"
            )
        return kept

    return policy


class _StripPlaceholderAuthTransport(httpx.AsyncBaseTransport):
    """Drops ``Authorization: Bearer x402``, a placeholder API key that must never reach the server."""

    def __init__(self, transport: httpx.AsyncBaseTransport) -> None:
        self._transport = transport

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.headers.get("authorization") == "Bearer x402":
            del request.headers["authorization"]
        return await self._transport.handle_async_request(request)

    async def aclose(self) -> None:
        await self._transport.aclose()


def create_payment_client(
    private_key: str,
    *,
    max_amount: int | None = None,
    allowed_pay_to: Iterable[str] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    **kwargs: Any,
) -> httpx.AsyncClient:
    """Create an httpx.AsyncClient that pays x402 v2 challenges (exact + upto on Base) transparently.

    Raises ``PaymentLimitError`` instead of signing when no offered payment fits the limits.
    """
    signer = EthAccountSigner(Account.from_key(private_key))
    client = x402Client()
    client.register(BASE_NETWORK, ExactEvmClientScheme(signer))
    client.register(BASE_NETWORK, UptoEvmClientScheme(signer))
    # The SDK's default spend controls cap every payment at $1; limits are only the ones passed here.
    client.set_spend_controls(False)
    if max_amount is not None or allowed_pay_to is not None:
        client.register_policy(spending_policy(max_amount, allowed_pay_to))

    inner = _StripPlaceholderAuthTransport(transport or httpx.AsyncHTTPTransport())
    return httpx.AsyncClient(transport=x402AsyncTransport(client, inner), **kwargs)
