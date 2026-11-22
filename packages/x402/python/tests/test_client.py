import base64
import json
from typing import Any

import httpx
import pytest

from libertai_x402 import PaymentLimitError, create_payment_client

PRIVATE_KEY = "0x0ee876735a3d8ea5507a6e984ed60e7f16ceb60aca56546f2dbcac61ebd40730"
PAY_TO = "0x1234567890123456789012345678901234567890"
URL = "https://api.libertai.io/v1/chat/completions"
USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

UPTO = {
    "scheme": "upto",
    "network": "eip155:8453",
    "amount": "1000",
    "payTo": PAY_TO,
    "maxTimeoutSeconds": 300,
    "asset": USDC,
    "extra": {
        "name": "USD Coin",
        "version": "2",
        "assetTransferMethod": "permit2",
        "facilitatorAddress": "0x9999999999999999999999999999999999999999",
    },
}

EXACT = {
    "scheme": "exact",
    "network": "eip155:8453",
    "amount": "5000",
    "payTo": PAY_TO,
    "maxTimeoutSeconds": 300,
    "asset": USDC,
    "extra": {"name": "USD Coin", "version": "2"},
}


def _b64(value: Any) -> str:
    return base64.b64encode(json.dumps(value).encode()).decode()


def _payment_required(accepts: list[dict[str, Any]]) -> httpx.Response:
    header = _b64(
        {
            "x402Version": 2,
            "resource": {
                "url": URL,
                "description": "chat",
                "mimeType": "application/json",
            },
            "accepts": accepts,
        }
    )
    return httpx.Response(402, headers={"PAYMENT-REQUIRED": header}, json={})


class _Server:
    def __init__(self, accepts: list[dict[str, Any]]) -> None:
        self.accepts = accepts
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if "payment-signature" in request.headers:
            return httpx.Response(200, json={"ok": True})
        return _payment_required(self.accepts)


def _decode_signature(request: httpx.Request) -> dict[str, Any]:
    return json.loads(base64.b64decode(request.headers["payment-signature"]))


async def _post(server: _Server, **kwargs: Any) -> httpx.Response:
    async with create_payment_client(
        PRIVATE_KEY, transport=httpx.MockTransport(server), **kwargs
    ) as client:
        return await client.post(
            URL,
            json={"model": "test", "messages": []},
            headers={"Authorization": "Bearer x402"},
        )


async def test_pays_upto_v2_challenge() -> None:
    server = _Server([UPTO])
    response = await _post(server)

    assert response.status_code == 200
    assert len(server.requests) == 2
    first, retry = server.requests
    assert "authorization" not in first.headers
    assert "authorization" not in retry.headers
    assert "x-payment" not in retry.headers
    assert json.loads(retry.content) == {"model": "test", "messages": []}

    payment = _decode_signature(retry)
    assert payment["x402Version"] == 2
    assert payment["accepted"]["scheme"] == "upto"
    assert payment["accepted"]["network"] == "eip155:8453"
    assert payment["accepted"]["amount"] == "1000"
    assert payment["accepted"]["payTo"] == PAY_TO
    assert payment["payload"]["signature"].startswith("0x")


async def test_pays_exact_v2_challenge() -> None:
    server = _Server([EXACT])
    response = await _post(server)

    assert response.status_code == 200
    payment = _decode_signature(server.requests[1])
    assert payment["x402Version"] == 2
    assert payment["accepted"]["scheme"] == "exact"
    assert payment["payload"]["authorization"]["value"] == "5000"


async def test_max_amount_blocks_signing() -> None:
    server = _Server([UPTO])
    with pytest.raises(PaymentLimitError, match="no payment option within limits"):
        await _post(server, max_amount=999)
    assert len(server.requests) == 1


async def test_max_amount_picks_affordable_option() -> None:
    server = _Server([EXACT, UPTO])
    response = await _post(server, max_amount=1000)

    assert response.status_code == 200
    assert _decode_signature(server.requests[1])["accepted"]["scheme"] == "upto"


async def test_allowed_pay_to_blocks_signing() -> None:
    server = _Server([UPTO])
    with pytest.raises(PaymentLimitError):
        await _post(
            server, allowed_pay_to=["0x0000000000000000000000000000000000000001"]
        )
    assert len(server.requests) == 1


async def test_allowed_pay_to_is_case_insensitive() -> None:
    server = _Server([UPTO])
    response = await _post(server, allowed_pay_to=[PAY_TO.upper().replace("0X", "0x")])
    assert response.status_code == 200


async def test_preserves_real_authorization() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200)

    async with create_payment_client(
        PRIVATE_KEY, transport=httpx.MockTransport(handler)
    ) as client:
        await client.get(URL, headers={"Authorization": "Bearer sk-real"})
    assert seen[0].headers["authorization"] == "Bearer sk-real"
