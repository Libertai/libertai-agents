# libertai-x402

[x402](https://www.x402.org/) utilities that handle payments automatically for LibertAI services

## Install

```bash
pip install libertai-x402
```

> **0.2.0 is a breaking release**: the client now speaks standard x402 v2 (`PAYMENT-REQUIRED` / `PAYMENT-SIGNATURE` headers) and is built on the official [`x402`](https://pypi.org/project/x402/) package. 0.1.x clients cannot pay the current LibertAI API.

> **0.2.1 changes the default behaviour**: payment limits now apply unless you change them (see [Payment limits](#payment-limits)). Payments to anything other than the LibertAI API, or above 5 USDC, are refused by default, and passing `None` now disables a limit instead of meaning "no limit configured".

## Prerequisite: Permit2 approval

Chat endpoints use the `upto` scheme, which settles through [Permit2](https://docs.uniswap.org/contracts/permit2/overview). Before the first `upto` payment, the paying wallet must approve the Permit2 contract `0x000000000022D473030F116dDEE9F6B43aC78BA3` to spend its Base USDC (`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`), once. Fixed-price endpoints (images, TTS, embeddings) use the `exact` scheme (EIP-3009) and need no approval.

## Usage with OpenAI SDK

```python
import asyncio
from openai import AsyncOpenAI
from libertai_x402 import create_payment_client

async def main():
    http_client = create_payment_client("0x...")

    client = AsyncOpenAI(
        base_url="https://api.libertai.io/v1",
        api_key="x402",
        http_client=http_client,
    )

    response = await client.chat.completions.create(
        model="qwen3.5-27b",
        messages=[{"role": "user", "content": "Hello!"}],
    )

    print(response.choices[0].message.content)

asyncio.run(main())
```

Set `api_key` to `"x402"` — the wrapper strips this dummy value before sending requests. Real API keys (any other value) are preserved.

## Usage with httpx

```python
import asyncio
from libertai_x402 import create_payment_client

async def main():
    async with create_payment_client("0x...") as client:
        resp = await client.post(
            "https://api.libertai.io/v1/chat/completions",
            json={
                "model": "qwen3.5-27b",
                "messages": [{"role": "user", "content": "Hello!"}],
            },
        )
        print(resp.json())

asyncio.run(main())
```

## Payment limits

Every payment is checked before it is signed or sent. Defaults target the LibertAI API:

| Kwarg                 | Default                                                             | Check                                                                          |
| --------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `allowed_origins`     | `(LIBERTAI_API_ORIGIN,)` (`https://api.libertai.io`)                | only 402s from these origins are paid, and signed payments are only sent there |
| `allowed_pay_to`      | `(LIBERTAI_PAY_TO,)` (`0x48E5A3e497D0C092D5B0Ba22B5A86ADA94227DFa`) | recipient (case-insensitive)                                                   |
| `max_amount`          | `DEFAULT_MAX_AMOUNT` (`5_000_000`, 5 USDC)                          | atomic USDC units (6 decimals) per payment                                     |
| `max_timeout_seconds` | `DEFAULT_MAX_TIMEOUT_SECONDS` (`86400`)                             | signature validity requested by the server                                     |

Extend a default with the exported constants, or pass `None` to disable a check:

```python
from libertai_x402 import LIBERTAI_API_ORIGIN, LIBERTAI_PAY_TO, create_payment_client

client = create_payment_client(
    "0x...",
    allowed_origins=[LIBERTAI_API_ORIGIN, "https://other.example"],
    allowed_pay_to=[LIBERTAI_PAY_TO, "0x..."],
    max_amount=100_000,  # at most $0.10 per payment
    max_timeout_seconds=None,  # no timeout check
)
```

If a payment falls outside the limits, nothing is signed or sent and `libertai_x402.PaymentLimitError` is raised. Requests that are not answered with `402` work for any origin.

## How it works

1. Makes the request normally
2. If the server responds with `402`, decodes the payment requirements from the `PAYMENT-REQUIRED` header
3. Signs an `exact` (EIP-3009) or `upto` (Permit2) payment on Base (`eip155:8453`) with the provided private key
4. Retries the request with the signed payment in the `PAYMENT-SIGNATURE` header

## License

MIT
