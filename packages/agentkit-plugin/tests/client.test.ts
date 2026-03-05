import type { Hex } from "viem";
import { beforeEach, describe, expect, it, vi } from "vitest";

const TEST_PRIVATE_KEY: Hex =
  "0x0ee876735a3d8ea5507a6e984ed60e7f16ceb60aca56546f2dbcac61ebd40730";

// Mock global fetch before any imports
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// Sample 402 response matching thirdweb format
const MOCK_REQUIREMENTS = {
  scheme: "upto",
  network: "eip155:8453",
  maxAmountRequired: "1000",
  resource: "https://api.libertai.io/v1/chat/completions",
  payTo: "0x1234567890123456789012345678901234567890",
  maxTimeoutSeconds: 300,
  asset: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
  extra: {
    name: "USD Coin",
    version: "2",
    primaryType: "TransferWithAuthorization",
  },
};

function make402Response() {
  return new Response(
    JSON.stringify({ x402Version: 2, accepts: [MOCK_REQUIREMENTS] }),
    { status: 402, headers: { "Content-Type": "application/json" } },
  );
}

function make200Response() {
  return new Response(
    JSON.stringify({ choices: [{ message: { content: "hi" } }] }),
    { status: 200, headers: { "Content-Type": "application/json" } },
  );
}

describe("createLLMClient", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns an OpenAI instance with default baseURL", async () => {
    const { createLLMClient } = await import("../src/client.js");
    const client = createLLMClient(TEST_PRIVATE_KEY);

    expect(client).toBeDefined();
    expect(client.chat).toBeDefined();
    expect(client.chat.completions).toBeDefined();
    expect(client.baseURL).toBe("https://api.libertai.io/v1");
  });

  it("accepts custom baseURL", async () => {
    const { createLLMClient } = await import("../src/client.js");
    const client = createLLMClient(TEST_PRIVATE_KEY, {
      baseURL: "https://custom.api/v1",
    });

    expect(client.baseURL).toBe("https://custom.api/v1");
  });

  it("passes through non-402 responses", async () => {
    const { createLLMClient } = await import("../src/client.js");
    const client = createLLMClient(TEST_PRIVATE_KEY);

    mockFetch.mockResolvedValueOnce(make200Response());

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const fetchFn = (client as any).fetch as typeof fetch;
    const result = await fetchFn(
      "https://api.libertai.io/v1/chat/completions",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: "test", messages: [] }),
      },
    );

    expect(result.status).toBe(200);
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("handles 402 by signing and retrying with X-PAYMENT header", async () => {
    const { createLLMClient } = await import("../src/client.js");
    const client = createLLMClient(TEST_PRIVATE_KEY);

    mockFetch
      .mockResolvedValueOnce(make402Response())
      .mockResolvedValueOnce(make200Response());

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const fetchFn = (client as any).fetch as typeof fetch;
    const result = await fetchFn(
      "https://api.libertai.io/v1/chat/completions",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer x402",
        },
        body: JSON.stringify({ model: "test", messages: [] }),
      },
    );

    expect(result.status).toBe(200);
    expect(mockFetch).toHaveBeenCalledTimes(2);

    // Verify retry request has X-PAYMENT header and no Authorization
    const retryCall = mockFetch.mock.calls[1][0] as Request;
    expect(retryCall.headers.get("X-PAYMENT")).toBeTruthy();
    expect(retryCall.headers.get("Authorization")).toBeNull();

    // Verify X-PAYMENT is valid JSON with expected structure
    const payment = JSON.parse(retryCall.headers.get("X-PAYMENT")!);
    expect(payment.x402Version).toBe(2);
    expect(payment.scheme).toBe("upto");
    expect(payment.network).toBe("eip155:8453");
    expect(payment.payload.signature).toBeTruthy();
    expect(payment.payload.authorization.from).toBeTruthy();
    expect(payment.payload.authorization.to).toBe(MOCK_REQUIREMENTS.payTo);
  });

  it("strips Authorization header on initial request", async () => {
    const { createLLMClient } = await import("../src/client.js");
    const client = createLLMClient(TEST_PRIVATE_KEY);

    mockFetch.mockResolvedValueOnce(make200Response());

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const fetchFn = (client as any).fetch as typeof fetch;
    await fetchFn("https://api.libertai.io/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer x402",
      },
      body: JSON.stringify({ model: "test", messages: [] }),
    });

    const req = mockFetch.mock.calls[0][0] as Request;
    expect(req.headers.get("Authorization")).toBeNull();
  });

  it("throws on 402 without accepts array", async () => {
    const { createLLMClient } = await import("../src/client.js");
    const client = createLLMClient(TEST_PRIVATE_KEY);

    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: "bad" }), {
        status: 402,
        headers: { "Content-Type": "application/json" },
      }),
    );

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const fetchFn = (client as any).fetch as typeof fetch;
    await expect(
      fetchFn("https://api.libertai.io/v1/chat/completions", {
        method: "POST",
        body: "{}",
      }),
    ).rejects.toThrow("x402: 402 response missing accepts[0]");
  });
});
