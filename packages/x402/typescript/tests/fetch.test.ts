import type { Hex } from "viem";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { wrapFetchWithPayment } from "../src/fetch.js";

const TEST_PRIVATE_KEY: Hex =
  "0x0ee876735a3d8ea5507a6e984ed60e7f16ceb60aca56546f2dbcac61ebd40730";
const PAY_TO = "0x1234567890123456789012345678901234567890";
const URL = "https://api.libertai.io/v1/chat/completions";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

const UPTO_REQUIREMENTS = {
  scheme: "upto",
  network: "eip155:8453",
  amount: "1000",
  payTo: PAY_TO,
  maxTimeoutSeconds: 300,
  asset: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
  extra: {
    name: "USD Coin",
    version: "2",
    assetTransferMethod: "permit2",
    facilitatorAddress: "0x9999999999999999999999999999999999999999",
  },
};

const EXACT_REQUIREMENTS = {
  scheme: "exact",
  network: "eip155:8453",
  amount: "5000",
  payTo: PAY_TO,
  maxTimeoutSeconds: 300,
  asset: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
  extra: { name: "USD Coin", version: "2" },
};

function b64(value: unknown): string {
  return Buffer.from(JSON.stringify(value)).toString("base64");
}

function make402Response(accepts: unknown[]) {
  const paymentRequired = {
    x402Version: 2,
    resource: { url: URL, description: "chat", mimeType: "application/json" },
    accepts,
  };
  return new Response(JSON.stringify({}), {
    status: 402,
    headers: {
      "Content-Type": "application/json",
      "PAYMENT-REQUIRED": b64(paymentRequired),
    },
  });
}

function make200Response() {
  return new Response(
    JSON.stringify({ choices: [{ message: { content: "hi" } }] }),
    { status: 200, headers: { "Content-Type": "application/json" } },
  );
}

function decodePaymentSignature(req: Request) {
  const header = req.headers.get("PAYMENT-SIGNATURE");
  expect(header).toBeTruthy();
  return JSON.parse(Buffer.from(header!, "base64").toString("utf8"));
}

const chatInit = (authorization?: string): RequestInit => ({
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    ...(authorization ? { Authorization: authorization } : {}),
  },
  body: JSON.stringify({ model: "test", messages: [] }),
});

describe("wrapFetchWithPayment", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("passes through non-402 responses", async () => {
    const fetchFn = wrapFetchWithPayment(TEST_PRIVATE_KEY);
    mockFetch.mockResolvedValueOnce(make200Response());

    const result = await fetchFn(URL, chatInit());

    expect(result.status).toBe(200);
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("pays an upto v2 challenge with a PAYMENT-SIGNATURE header", async () => {
    const fetchFn = wrapFetchWithPayment(TEST_PRIVATE_KEY);
    mockFetch
      .mockResolvedValueOnce(make402Response([UPTO_REQUIREMENTS]))
      .mockResolvedValueOnce(make200Response());

    const result = await fetchFn(URL, chatInit("Bearer x402"));

    expect(result.status).toBe(200);
    expect(mockFetch).toHaveBeenCalledTimes(2);

    const retry = mockFetch.mock.calls[1][0] as Request;
    expect(retry.headers.get("Authorization")).toBeNull();
    expect(retry.headers.get("X-PAYMENT")).toBeNull();
    expect(await retry.text()).toBe(
      JSON.stringify({ model: "test", messages: [] }),
    );

    const payment = decodePaymentSignature(retry);
    expect(payment.x402Version).toBe(2);
    expect(payment.accepted).toMatchObject({
      scheme: "upto",
      network: "eip155:8453",
      amount: "1000",
      payTo: PAY_TO,
    });
    expect(payment.payload.signature).toMatch(/^0x[0-9a-f]+$/);
  });

  it("pays an exact v2 challenge", async () => {
    const fetchFn = wrapFetchWithPayment(TEST_PRIVATE_KEY);
    mockFetch
      .mockResolvedValueOnce(make402Response([EXACT_REQUIREMENTS]))
      .mockResolvedValueOnce(make200Response());

    await fetchFn(URL, chatInit());

    const payment = decodePaymentSignature(mockFetch.mock.calls[1][0]);
    expect(payment.x402Version).toBe(2);
    expect(payment.accepted.scheme).toBe("exact");
    expect(payment.payload.authorization.to).toBe(PAY_TO);
    expect(payment.payload.authorization.value).toBe("5000");
  });

  it("refuses to sign above maxAmount", async () => {
    const fetchFn = wrapFetchWithPayment(TEST_PRIVATE_KEY, {
      maxAmount: 999n,
    });
    mockFetch.mockResolvedValueOnce(make402Response([UPTO_REQUIREMENTS]));

    await expect(fetchFn(URL, chatInit())).rejects.toThrow(
      /no payment option within limits/,
    );
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("picks the option that fits maxAmount", async () => {
    const fetchFn = wrapFetchWithPayment(TEST_PRIVATE_KEY, {
      maxAmount: "1000",
    });
    mockFetch
      .mockResolvedValueOnce(
        make402Response([EXACT_REQUIREMENTS, UPTO_REQUIREMENTS]),
      )
      .mockResolvedValueOnce(make200Response());

    await fetchFn(URL, chatInit());

    const payment = decodePaymentSignature(mockFetch.mock.calls[1][0]);
    expect(payment.accepted.scheme).toBe("upto");
  });

  it("refuses to sign for a payTo outside allowedPayTo", async () => {
    const fetchFn = wrapFetchWithPayment(TEST_PRIVATE_KEY, {
      allowedPayTo: ["0x0000000000000000000000000000000000000001"],
    });
    mockFetch.mockResolvedValueOnce(make402Response([UPTO_REQUIREMENTS]));

    await expect(fetchFn(URL, chatInit())).rejects.toThrow(
      /no payment option within limits/,
    );
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("matches allowedPayTo case-insensitively", async () => {
    const fetchFn = wrapFetchWithPayment(TEST_PRIVATE_KEY, {
      allowedPayTo: [PAY_TO.toUpperCase().replace("0X", "0x")],
    });
    mockFetch
      .mockResolvedValueOnce(make402Response([UPTO_REQUIREMENTS]))
      .mockResolvedValueOnce(make200Response());

    const result = await fetchFn(URL, chatInit());
    expect(result.status).toBe(200);
  });

  it("strips Authorization only when value is 'Bearer x402'", async () => {
    const fetchFn = wrapFetchWithPayment(TEST_PRIVATE_KEY);
    mockFetch
      .mockResolvedValueOnce(make200Response())
      .mockResolvedValueOnce(make200Response());

    await fetchFn(URL, chatInit("Bearer x402"));
    await fetchFn(URL, chatInit("Bearer sk-real-api-key"));

    expect(
      (mockFetch.mock.calls[0][0] as Request).headers.get("Authorization"),
    ).toBeNull();
    expect(
      (mockFetch.mock.calls[1][0] as Request).headers.get("Authorization"),
    ).toBe("Bearer sk-real-api-key");
  });

  it("throws on a 402 without a PAYMENT-REQUIRED header", async () => {
    const fetchFn = wrapFetchWithPayment(TEST_PRIVATE_KEY);
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: "bad" }), {
        status: 402,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(fetchFn(URL, chatInit())).rejects.toThrow(
      /Failed to parse payment requirements/,
    );
  });
});
