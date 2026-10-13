from __future__ import annotations

import json

import httpx
import pytest
from eth_account import Account
from eth_account.messages import encode_typed_data

from libertai_x402 import PaymentPolicy, PaymentRejectedError
from libertai_x402 import client as client_module
from libertai_x402 import sign as sign_module

TEST_PRIVATE_KEY = "0x0ee876735a3d8ea5507a6e984ed60e7f16ceb60aca56546f2dbcac61ebd40730"
ACCOUNT = Account.from_key(TEST_PRIVATE_KEY)
API_URL = "https://api.libertai.io/v1/chat/completions"
USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
FACILITATOR = "0xC945bd3145765BEB047aEb44f4F13d84865cf714"
ATTACKER = "0x9999999999999999999999999999999999999999"
MAX_UINT = str(2**256 - 1)

USDC_DOMAIN = {
    "name": "USD Coin",
    "version": "2",
    "chainId": 8453,
    "verifyingContract": USDC,
}
PERMIT_TYPES = {
    "Permit": [
        {"name": "owner", "type": "address"},
        {"name": "spender", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "nonce", "type": "uint256"},
        {"name": "deadline", "type": "uint256"},
    ],
}

# Live shape of api.libertai.io's `upto` 402.
LIBERTAI_UPTO = {
    "scheme": "upto",
    "network": "eip155:8453",
    "maxAmountRequired": "100",
    "resource": API_URL,
    "payTo": FACILITATOR,
    "maxTimeoutSeconds": 86400,
    "asset": USDC,
    "extra": {"name": "USD Coin", "version": "2", "primaryType": "Permit"},
}


@pytest.fixture(autouse=True)
def _no_rpc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sign_module, "_get_permit_nonce", lambda asset, owner: 7)


def _client(
    accepts: list[dict], calls: list[httpx.Request], policy: PaymentPolicy | None = None
) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if "x-payment" in request.headers:
            return httpx.Response(200, text="ok")
        return httpx.Response(402, json={"x402Version": 2, "accepts": accepts})

    transport = client_module._PaymentTransport(
        TEST_PRIVATE_KEY, httpx.MockTransport(handler), policy or PaymentPolicy()
    )
    return httpx.AsyncClient(transport=transport)


def _recover_permit(header: dict, spender: str, value: int) -> str:
    message = {
        "owner": ACCOUNT.address,
        "spender": spender,
        "value": value,
        "nonce": 7,
        "deadline": int(header["payload"]["authorization"]["validBefore"]),
    }
    signable = encode_typed_data(
        domain_data=USDC_DOMAIN, message_types=PERMIT_TYPES, message_data=message
    )
    return Account.recover_message(signable, signature=header["payload"]["signature"])


@pytest.mark.anyio
async def test_signs_libertai_upto_permit_for_facilitator() -> None:
    calls: list[httpx.Request] = []
    async with _client([LIBERTAI_UPTO], calls) as c:
        resp = await c.post(API_URL, json={})
    assert resp.status_code == 200
    header = json.loads(calls[1].headers["x-payment"])
    assert _recover_permit(header, FACILITATOR, 100) == ACCOUNT.address


@pytest.mark.anyio
async def test_refuses_reported_unlimited_permit_from_foreign_origin() -> None:
    # Reproduction from the private disclosure.
    calls: list[httpx.Request] = []
    evil = {
        **LIBERTAI_UPTO,
        "payTo": ATTACKER,
        "maxAmountRequired": MAX_UINT,
        "maxTimeoutSeconds": 31536000,
    }
    async with _client([evil], calls) as c:
        with pytest.raises(PaymentRejectedError, match="refusing to pay"):
            await c.post("http://127.0.0.1:8402/data", json={})
    assert len(calls) == 1


@pytest.mark.anyio
async def test_refuses_attacker_permit_even_from_libertai_origin() -> None:
    calls: list[httpx.Request] = []
    evil = {**LIBERTAI_UPTO, "payTo": ATTACKER, "maxAmountRequired": MAX_UINT}
    async with _client([evil], calls) as c:
        with pytest.raises(PaymentRejectedError, match="not in allowed_payees"):
            await c.post(API_URL, json={})
    assert len(calls) == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("override", "error"),
    [
        ({"maxAmountRequired": "5000001"}, "exceeds max_amount"),
        ({"maxAmountRequired": "0"}, "exceeds max_amount"),
        ({"maxTimeoutSeconds": 86401}, "maxTimeoutSeconds"),
        ({"network": "eip155:1"}, "unsupported network"),
        ({"asset": "0x0000000000000000000000000000000000000001"}, "unsupported asset"),
        ({"extra": {"primaryType": "SetApprovalForAll"}}, "unsupported primaryType"),
    ],
)
async def test_refuses_out_of_policy_requirements(override: dict, error: str) -> None:
    calls: list[httpx.Request] = []
    async with _client([{**LIBERTAI_UPTO, **override}], calls) as c:
        with pytest.raises(PaymentRejectedError, match=error):
            await c.post(API_URL, json={})
    assert len(calls) == 1


@pytest.mark.anyio
async def test_ignores_domain_advertised_by_402() -> None:
    calls: list[httpx.Request] = []
    req = {**LIBERTAI_UPTO, "extra": {"name": "Evil", "version": "9", "primaryType": "Permit"}}
    async with _client([req], calls) as c:
        await c.post(API_URL, json={})
    header = json.loads(calls[1].headers["x-payment"])
    assert _recover_permit(header, FACILITATOR, 100) == ACCOUNT.address


@pytest.mark.anyio
async def test_picks_first_acceptable_entry() -> None:
    calls: list[httpx.Request] = []
    async with _client([{**LIBERTAI_UPTO, "payTo": ATTACKER}, LIBERTAI_UPTO], calls) as c:
        resp = await c.post(API_URL, json={})
    assert resp.status_code == 200
    header = json.loads(calls[1].headers["x-payment"])
    assert header["payload"]["authorization"]["to"] == FACILITATOR


@pytest.mark.anyio
async def test_custom_policy_allows_other_origin_payee_and_cap() -> None:
    payee = "0x1234567890123456789012345678901234567890"
    calls: list[httpx.Request] = []
    req = {
        **LIBERTAI_UPTO,
        "payTo": payee,
        "maxAmountRequired": "10000000",
        "extra": {"primaryType": "TransferWithAuthorization"},
    }
    policy = PaymentPolicy(
        allowed_origins=["https://x402.example.com"],
        allowed_payees=[payee],
        max_amount=10_000_000,
    )
    async with _client([req], calls, policy) as c:
        resp = await c.post("https://x402.example.com/data", json={})
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_null_extra_signs_transfer_with_authorization() -> None:
    calls: list[httpx.Request] = []
    async with _client([{**LIBERTAI_UPTO, "extra": None}], calls) as c:
        resp = await c.post(API_URL, json={})
    assert resp.status_code == 200
    header = json.loads(calls[1].headers["x-payment"])
    assert header["payload"]["authorization"]["validAfter"] != "0"


@pytest.mark.anyio
async def test_malformed_entries_are_rejected_not_crashing() -> None:
    calls: list[httpx.Request] = []
    accepts = ["nope", {**LIBERTAI_UPTO, "extra": "nope"}]
    async with _client(accepts, calls) as c:
        with pytest.raises(PaymentRejectedError, match="malformed.*'extra' must be an object"):
            await c.post(API_URL, json={})


@pytest.mark.anyio
async def test_non_object_402_body_raises_value_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json=["nope"])

    transport = client_module._PaymentTransport(
        TEST_PRIVATE_KEY, httpx.MockTransport(handler), PaymentPolicy()
    )
    async with httpx.AsyncClient(transport=transport) as c:
        with pytest.raises(ValueError, match="missing accepts"):
            await c.post(API_URL, json={})

