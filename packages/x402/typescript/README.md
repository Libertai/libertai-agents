# @libertai/x402

[x402](https://www.x402.org/) utilities that handle payments automatically for LibertAI services

## Install

```bash
npm install @libertai/x402
```

> **0.2.0 is a breaking release**: the client now speaks standard x402 v2 (`PAYMENT-REQUIRED` / `PAYMENT-SIGNATURE` headers) and is built on the official [`@x402/fetch`](https://www.npmjs.com/package/@x402/fetch) and [`@x402/evm`](https://www.npmjs.com/package/@x402/evm) packages. 0.1.x clients cannot pay the current LibertAI API.

## Prerequisite: Permit2 approval

Chat endpoints use the `upto` scheme, which settles through [Permit2](https://docs.uniswap.org/contracts/permit2/overview). Before the first `upto` payment, the paying wallet must approve the Permit2 contract `0x000000000022D473030F116dDEE9F6B43aC78BA3` to spend its Base USDC (`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`), once. Fixed-price endpoints (images, TTS, embeddings) use the `exact` scheme (EIP-3009) and need no approval.

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

By default every payment the server asks for is signed. Pass limits to refuse anything else:

```typescript
const fetchWithPayment = wrapFetchWithPayment("0x...", {
  maxAmount: 100_000n, // atomic USDC units (6 decimals): at most $0.10 per payment
  allowedPayTo: ["0x..."], // only pay these recipients
});
```

If no payment option offered by the server fits, nothing is signed and the call throws.

## How it works

1. Makes the request normally
2. If the server responds with `402`, decodes the payment requirements from the `PAYMENT-REQUIRED` header
3. Signs an `exact` (EIP-3009) or `upto` (Permit2) payment on Base (`eip155:8453`) with the provided private key
4. Retries the request with the signed payment in the `PAYMENT-SIGNATURE` header

## License

MIT
