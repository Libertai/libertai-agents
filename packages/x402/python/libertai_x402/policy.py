from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import httpx
from eth_utils import is_address, to_checksum_address

from libertai_x402.types import PaymentRequirements

BASE_NETWORK = "eip155:8453"
BASE_CHAIN_ID = 8453

# USDC on Base. The EIP-712 domain is pinned here and never taken from a 402
# response: a server must not be able to choose which contract we sign for.
USDC_BASE_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
USDC_BASE_NAME = "USD Coin"
USDC_BASE_VERSION = "2"

LIBERTAI_ORIGINS = ("https://api.libertai.io",)

# LibertAI's x402 facilitator (Permit spender for the `upto` scheme) and
# recipient wallet.
LIBERTAI_PAYEES = (
    "0xC945bd3145765BEB047aEb44f4F13d84865cf714",
    "0x48E5A3e497D0C092D5B0Ba22B5A86ADA94227DFa",
)

DEFAULT_MAX_AMOUNT = 5_000_000  # 5 USDC per request
DEFAULT_MAX_TIMEOUT_SECONDS = 86_400  # 1 day

_SUPPORTED_PRIMARY_TYPES = ("TransferWithAuthorization", "Permit")


class PaymentRejectedError(ValueError):
    def __init__(self, message: str) -> None:
        super().__init__(f"x402: {message}")


def _origin(url: str | httpx.URL) -> str:
    u = httpx.URL(url)
    default_port = {"http": 80, "https": 443}.get(u.scheme)
    port = f":{u.port}" if u.port is not None and u.port != default_port else ""
    return f"{u.scheme}://{u.host}{port}"


@dataclass(frozen=True)
class PaymentPolicy:
    """Limits on what the client will sign in response to a 402."""

    allowed_origins: Iterable[str] = LIBERTAI_ORIGINS
    allowed_payees: Iterable[str] = LIBERTAI_PAYEES
    # USDC atomic units (6 decimals)
    max_amount: int = DEFAULT_MAX_AMOUNT
    max_timeout_seconds: int = DEFAULT_MAX_TIMEOUT_SECONDS
    _origins: frozenset[str] = field(init=False, repr=False)
    _payees: frozenset[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "_origins", frozenset(_origin(o) for o in self.allowed_origins)
        )
        object.__setattr__(
            self,
            "_payees",
            frozenset(to_checksum_address(a) for a in self.allowed_payees),
        )

    def check_origin(self, url: str | httpx.URL) -> None:
        origin = _origin(url)
        if origin not in self._origins:
            raise PaymentRejectedError(
                f"refusing to pay {origin}: not in allowed_origins"
            )

    def reject_reason(self, req: PaymentRequirements) -> str | None:
        """Return why a requirement is rejected, or None if it may be signed."""
        if req.network != BASE_NETWORK:
            return f"unsupported network {req.network}"
        if not is_address(req.asset) or to_checksum_address(
            req.asset
        ) != to_checksum_address(USDC_BASE_ADDRESS):
            return f"unsupported asset {req.asset}"
        if req.primary_type not in _SUPPORTED_PRIMARY_TYPES:
            return f"unsupported primaryType {req.primary_type}"
        if not is_address(req.payTo) or to_checksum_address(req.payTo) not in self._payees:
            return f"payee {req.payTo} not in allowed_payees"
        try:
            amount = int(req.maxAmountRequired)
        except (TypeError, ValueError):
            return f"invalid amount {req.maxAmountRequired}"
        if amount <= 0 or amount > self.max_amount:
            return f"amount {req.maxAmountRequired} exceeds max_amount {self.max_amount}"
        timeout = req.maxTimeoutSeconds
        if (
            not isinstance(timeout, int)
            or isinstance(timeout, bool)
            or timeout <= 0
            or timeout > self.max_timeout_seconds
        ):
            return f"maxTimeoutSeconds {timeout} exceeds {self.max_timeout_seconds}"
        return None

    def select(self, accepts: list[dict]) -> PaymentRequirements:
        reasons: list[str] = []
        for raw in accepts:
            if not isinstance(raw, dict):
                reasons.append("malformed requirements entry")
                continue
            try:
                req = PaymentRequirements.from_dict(raw)
            except (TypeError, ValueError) as e:
                reasons.append(str(e))
                continue
            reason = self.reject_reason(req)
            if reason is None:
                return req
            reasons.append(reason)
        raise PaymentRejectedError(
            f"no acceptable payment requirements ({'; '.join(reasons)})"
        )
