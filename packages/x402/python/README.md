# libertai-x402

[x402](https://www.x402.org/) utilities that handle payments automatically for LibertAI services

## Install

```bash
pip install libertai-x402
```

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

## Spending limits

The client only signs a payment when every check passes, and raises `PaymentRejectedError` otherwise:

- the request goes to an allowed origin (default: `https://api.libertai.io`)
- the payment is USDC on Base; the EIP-712 domain is pinned in the package and never read from the 402
- the payee (or Permit spender) is an allowed address (default: LibertAI's facilitator and wallet)
- the amount is at most `max_amount` (default: 5 USDC per request). The cap applies to each request; there is no running total
- the signature is valid for at most `max_timeout_seconds` (default: 1 day)

To pay another x402 service, allow it explicitly:

```python
from libertai_x402 import PaymentPolicy, create_payment_client

client = create_payment_client(
    "0x...",
    policy=PaymentPolicy(
        allowed_origins=["https://api.libertai.io", "https://x402.example.com"],
        allowed_payees=["0x..."],
        max_amount=10_000_000,  # 10 USDC, in atomic units (6 decimals)
    ),
)
```

## How it works

1. Makes the request normally
2. If the server responds with `402`, picks the first entry in `accepts` that passes the spending limits
3. Signs an EIP-712 typed data message (Permit or TransferWithAuthorization for USDC on Base) using the provided private key
4. Retries the request with the signed payment in the `X-PAYMENT` header

## License

MIT
