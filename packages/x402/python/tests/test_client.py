import base64
import json
from typing import Any

import httpx
import pytest

from libertai_x402 import (
    DEFAULT_MAX_AMOUNT,
    DEFAULT_MAX_TIMEOUT_SECONDS,
    LIBERTAI_API_ORIGIN,
    LIBERTAI_PAY_TO,
    PaymentLimitError,
    create_payment_client,
)

PRIVATE_KEY = "0x0ee876735a3d8ea5507a6e984ed60e7f16ceb60aca56546f2dbcac61ebd40730"
PAY_TO = LIBERTAI_PAY_TO
OTHER_PAY_TO = "0xabcdef0123456789abcdef0123456789abcdef01"
URL = "https://api.libertai.io/v1/chat/completions"
OTHER_URL = "https://evil.example/v1/chat/completions"
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


async def _post(server: _Server, url: str = URL, **kwargs: Any) -> httpx.Response:
    async with create_payment_client(
        PRIVATE_KEY, transport=httpx.MockTransport(server), **kwargs
    ) as client:
        return await client.post(
            url,
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
    server = _Server([{**UPTO, "payTo": OTHER_PAY_TO}])
    response = await _post(
        server, allowed_pay_to=[OTHER_PAY_TO.upper().replace("0X", "0x")]
    )
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


def test_default_constants() -> None:
    assert LIBERTAI_API_ORIGIN == "https://api.libertai.io"
    assert LIBERTAI_PAY_TO == "0x48E5A3e497D0C092D5B0Ba22B5A86ADA94227DFa"
    assert DEFAULT_MAX_AMOUNT == 5_000_000
    assert DEFAULT_MAX_TIMEOUT_SECONDS == 86400


async def test_pays_up_to_5_usdc_by_default() -> None:
    server = _Server([{**EXACT, "amount": "5000000"}])
    assert (await _post(server)).status_code == 200


async def test_refuses_more_than_5_usdc_by_default() -> None:
    server = _Server([{**EXACT, "amount": "5000001"}])
    with pytest.raises(PaymentLimitError, match="no payment option within limits"):
        await _post(server)
    assert len(server.requests) == 1


async def test_max_amount_none_disables_limit() -> None:
    server = _Server([{**EXACT, "amount": "5000001"}])
    assert (await _post(server, max_amount=None)).status_code == 200


async def test_refuses_other_pay_to_by_default() -> None:
    server = _Server([{**UPTO, "payTo": OTHER_PAY_TO}])
    with pytest.raises(PaymentLimitError, match="no payment option within limits"):
        await _post(server)
    assert len(server.requests) == 1


async def test_default_pay_to_is_case_insensitive() -> None:
    server = _Server([{**UPTO, "payTo": LIBERTAI_PAY_TO.lower()}])
    assert (await _post(server)).status_code == 200


async def test_allowed_pay_to_none_disables_check() -> None:
    server = _Server([{**UPTO, "payTo": OTHER_PAY_TO}])
    assert (await _post(server, allowed_pay_to=None)).status_code == 200


async def test_refuses_long_timeout_by_default() -> None:
    server = _Server([{**EXACT, "maxTimeoutSeconds": 86401}])
    with pytest.raises(PaymentLimitError, match="no payment option within limits"):
        await _post(server)
    assert len(server.requests) == 1


async def test_max_timeout_seconds_none_disables_check() -> None:
    server = _Server([{**EXACT, "maxTimeoutSeconds": 86401}])
    assert (await _post(server, max_timeout_seconds=None)).status_code == 200


async def test_refuses_402_from_other_origin() -> None:
    server = _Server([UPTO])
    with pytest.raises(
        PaymentLimitError, match="refusing to pay a 402 from non-allowed origin"
    ):
        await _post(server, url=OTHER_URL)
    assert len(server.requests) == 1


async def test_refuses_to_send_payment_to_other_origin() -> None:
    server = _Server([UPTO])
    async with create_payment_client(
        PRIVATE_KEY, transport=httpx.MockTransport(server)
    ) as client:
        with pytest.raises(PaymentLimitError, match="refusing to send a payment"):
            await client.get(OTHER_URL, headers={"PAYMENT-SIGNATURE": "signed"})
    assert server.requests == []


async def test_redirect_carrying_payment_to_other_origin_is_refused() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(302, headers={"Location": OTHER_URL})

    async with create_payment_client(
        PRIVATE_KEY, transport=httpx.MockTransport(handler), follow_redirects=True
    ) as client:
        with pytest.raises(PaymentLimitError, match="refusing to send a payment"):
            await client.get(URL, headers={"PAYMENT-SIGNATURE": "signed"})
    assert [str(r.url) for r in seen] == [URL]


async def test_redirect_after_paid_retry_is_not_paid_again() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.host == "evil.example":
            return _payment_required([UPTO])
        if "payment-signature" in request.headers:
            return httpx.Response(302, headers={"Location": OTHER_URL})
        return _payment_required([UPTO])

    async with create_payment_client(
        PRIVATE_KEY, transport=httpx.MockTransport(handler), follow_redirects=True
    ) as client:
        with pytest.raises(
            PaymentLimitError, match="refusing to pay a 402 from non-allowed origin"
        ):
            await client.post(URL, json={})
    assert [str(r.url) for r in seen] == [URL, URL, OTHER_URL]
    assert "payment-signature" not in seen[2].headers


async def test_non_402_from_other_origin_passes_through() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200)

    async with create_payment_client(
        PRIVATE_KEY, transport=httpx.MockTransport(handler)
    ) as client:
        response = await client.get(OTHER_URL)
    assert response.status_code == 200


async def test_pays_extra_allowed_origin() -> None:
    server = _Server([UPTO])
    response = await _post(
        server,
        url=OTHER_URL,
        allowed_origins=[LIBERTAI_API_ORIGIN, "https://evil.example/"],
    )
    assert response.status_code == 200
    assert str(server.requests[1].url) == OTHER_URL


async def test_allowed_origins_none_disables_check() -> None:
    server = _Server([UPTO])
    assert (await _post(server, url=OTHER_URL, allowed_origins=None)).status_code == 200
