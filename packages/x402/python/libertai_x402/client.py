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

BASE_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
"""USDC on Base, the only token the default limits allow."""

LIBERTAI_API_ORIGIN = "https://api.libertai.io"
LIBERTAI_PAY_TO = "0x48E5A3e497D0C092D5B0Ba22B5A86ADA94227DFa"
"""LibertAI's payment wallet, the ``payTo`` of every LibertAI API payment."""
DEFAULT_MAX_AMOUNT = 5_000_000
"""5 USDC in atomic units (6 decimals)."""
DEFAULT_MAX_TIMEOUT_SECONDS = 86400


class PaymentLimitError(PaymentError):
    """A payment was refused because it falls outside the configured limits."""


def spending_policy(
    max_amount: int | None = DEFAULT_MAX_AMOUNT,
    allowed_pay_to: Iterable[str] | None = (LIBERTAI_PAY_TO,),
    max_timeout_seconds: int | None = DEFAULT_MAX_TIMEOUT_SECONDS,
    allowed_assets: Iterable[str] | None = (BASE_USDC,),
) -> PaymentPolicy:
    """x402 policy keeping only requirements within ``max_amount`` (atomic units), ``allowed_pay_to``,
    ``max_timeout_seconds`` and ``allowed_assets``. ``None`` disables that check."""
    allowed = None if allowed_pay_to is None else {a.lower() for a in allowed_pay_to}

    assets = None if allowed_assets is None else {a.lower() for a in allowed_assets}

    def policy(_version: int, reqs: list[RequirementsView]) -> list[RequirementsView]:
        kept = [
            r
            for r in reqs
            if (max_amount is None or int(r.get_amount()) <= max_amount)
            and (allowed is None or r.pay_to.lower() in allowed)
            and (assets is None or r.asset.lower() in assets)
            and (
                max_timeout_seconds is None
                or r.max_timeout_seconds <= max_timeout_seconds
            )
        ]
        if not kept:
            offered = ", ".join(
                f"{r.get_amount()} of {r.asset} to {r.pay_to} (timeout {r.max_timeout_seconds}s)"
                for r in reqs
            )
            raise PaymentLimitError(
                f"x402: no payment option within limits (max_amount={max_amount}, "
                f"allowed_pay_to={sorted(allowed) if allowed is not None else 'any'}, "
                f"max_timeout_seconds={max_timeout_seconds}, "
                f"allowed_assets={sorted(assets) if assets is not None else 'any'}); offered: {offered}"
            )
        return kept

    return policy


def _origin(url: httpx.URL | str) -> str:
    url = httpx.URL(url)
    port = f":{url.port}" if url.port is not None else ""
    return f"{url.scheme}://{url.host}{port}"


class _GuardTransport(httpx.AsyncBaseTransport):
    """Drops ``Authorization: Bearer x402`` (a placeholder API key that must never reach the server) and
    enforces ``allowed_origins``.

    Every request the x402 transport sends goes through here, so origin checks cover its retries too.
    """

    def __init__(
        self, transport: httpx.AsyncBaseTransport, allowed_origins: Iterable[str] | None
    ) -> None:
        self._transport = transport
        self._allowed = (
            None if allowed_origins is None else {_origin(o) for o in allowed_origins}
        )

    def _is_allowed(self, url: httpx.URL) -> bool:
        return self._allowed is None or _origin(url) in self._allowed

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.headers.get("authorization") == "Bearer x402":
            del request.headers["authorization"]
        if "payment-signature" in request.headers and not self._is_allowed(request.url):
            raise PaymentLimitError(
                f"x402: refusing to send a payment to non-allowed origin {_origin(request.url)}"
            )
        response = await self._transport.handle_async_request(request)
        if "payment-signature" in request.headers and response.is_redirect:
            # Without a Location the client can't follow it: a redirect after paying must never
            # lead to another payment.
            del response.headers["location"]
        if response.status_code == 402 and not self._is_allowed(request.url):
            await response.aclose()
            raise PaymentLimitError(
                f"x402: refusing to pay a 402 from non-allowed origin {_origin(request.url)}"
            )
        return response

    async def aclose(self) -> None:
        await self._transport.aclose()


def create_payment_client(
    private_key: str,
    *,
    allowed_origins: Iterable[str] | None = (LIBERTAI_API_ORIGIN,),
    allowed_pay_to: Iterable[str] | None = (LIBERTAI_PAY_TO,),
    max_amount: int | None = DEFAULT_MAX_AMOUNT,
    max_timeout_seconds: int | None = DEFAULT_MAX_TIMEOUT_SECONDS,
    allowed_assets: Iterable[str] | None = (BASE_USDC,),
    transport: httpx.AsyncBaseTransport | None = None,
    **kwargs: Any,
) -> httpx.AsyncClient:
    """Create an httpx.AsyncClient that pays x402 v2 challenges (exact + upto on Base) transparently.

    Only 402s from ``allowed_origins`` are paid, and signed payments are only sent there. Passing ``None``
    for a limit disables it. Raises ``PaymentLimitError`` instead of signing or sending a payment outside
    the limits.
    """
    signer = EthAccountSigner(Account.from_key(private_key))
    client = x402Client()
    client.register(BASE_NETWORK, ExactEvmClientScheme(signer))
    client.register(BASE_NETWORK, UptoEvmClientScheme(signer))
    # The SDK's default spend controls cap every payment at $1; limits are only the spending policy's.
    client.set_spend_controls(False)
    client.register_policy(
        spending_policy(max_amount, allowed_pay_to, max_timeout_seconds, allowed_assets)
    )

    inner = _GuardTransport(transport or httpx.AsyncHTTPTransport(), allowed_origins)
    return httpx.AsyncClient(transport=x402AsyncTransport(client, inner), **kwargs)
