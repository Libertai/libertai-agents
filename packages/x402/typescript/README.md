# @libertai/x402

[x402](https://www.x402.org/) utilities that handle payments automatically for LibertAI services

## Install

```bash
npm install @libertai/x402
```

## Usage with OpenAI SDK

```typescript
import { wrapFetchWithPayment } from "@libertai/x402";
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "https://api.libertai.io/v1",
  apiKey: "x402",
  fetch: wrapFetchWithPayment(process.env.PRIVATE_KEY as `0x${string}`),
});

const response = await client.chat.completions.create({
  model: "qwen3.5-27b",
  messages: [{ role: "user", content: "Hello!" }],
});

console.log(response.choices[0].message.content);
```

Set `apiKey` to `"x402"` — the wrapper strips this dummy value before sending requests. Real API keys (any other value) are preserved.

## Usage with plain fetch

```typescript
import { wrapFetchWithPayment } from "@libertai/x402";

const fetchWithPayment = wrapFetchWithPayment("0x...");

const response = await fetchWithPayment(
  "https://api.libertai.io/v1/chat/completions",
  {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "qwen3.5-27b",
      messages: [{ role: "user", content: "Hello!" }],
    }),
  },
);
```

## Spending limits

The wrapper only signs a payment when every check passes, and throws `PaymentRejectedError` otherwise:

- the request goes to an allowed origin (default: `https://api.libertai.io`)
- the payment is USDC on Base; the EIP-712 domain is pinned in the package and never read from the 402
- the payee (or Permit spender) is an allowed address (default: LibertAI's facilitator and wallet)
- the amount is at most `maxAmount` (default: 5 USDC per request). The cap applies to each request; there is no running total
- the signature is valid for at most `maxTimeoutSeconds` (default: 1 day)

To pay another x402 service, allow it explicitly:

```typescript
const fetchWithPayment = wrapFetchWithPayment("0x...", {
  allowedOrigins: ["https://api.libertai.io", "https://x402.example.com"],
  allowedPayees: ["0x..."],
  maxAmount: 10_000_000n, // 10 USDC, in atomic units (6 decimals)
});
```

## How it works

1. Makes the request normally
2. If the server responds with `402`, picks the first entry in `accepts` that passes the spending limits
3. Signs an EIP-712 typed data message (Permit or TransferWithAuthorization for USDC on Base) using the provided private key
4. Retries the request with the signed payment in the `X-PAYMENT` header

## License

MIT
