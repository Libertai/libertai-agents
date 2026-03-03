import type { Hex } from "viem";
import { beforeEach, describe, expect, it, vi } from "vitest";

const TEST_PRIVATE_KEY: Hex =
  "0x0ee876735a3d8ea5507a6e984ed60e7f16ceb60aca56546f2dbcac61ebd40730";

const mockRegisterExactEvmScheme = vi.fn(
  (client: unknown) => client as unknown,
);
const mockWrapFetchWithPayment = vi.fn(
  () => (() => Promise.resolve(new Response())) as unknown as typeof fetch,
);

class MockX402Client {
  _mock = true;
}

vi.mock("@x402/fetch", () => ({
  x402Client: MockX402Client,
  wrapFetchWithPayment: mockWrapFetchWithPayment,
}));

vi.mock("@x402/evm/exact/client", () => ({
  registerExactEvmScheme: mockRegisterExactEvmScheme,
}));

describe("createLLMClient", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns an OpenAI instance", async () => {
    const { createLLMClient } = await import("../src/client.js");
    const client = createLLMClient(TEST_PRIVATE_KEY);

    expect(client).toBeDefined();
    expect(client.chat).toBeDefined();
    expect(client.chat.completions).toBeDefined();
  });

  it("uses default baseURL", async () => {
    const { createLLMClient } = await import("../src/client.js");
    const client = createLLMClient(TEST_PRIVATE_KEY);

    expect(client.baseURL).toBe("https://api.libertai.io/v1");
  });

  it("accepts custom baseURL", async () => {
    const { createLLMClient } = await import("../src/client.js");
    const client = createLLMClient(TEST_PRIVATE_KEY, {
      baseURL: "https://custom.api/v1",
    });

    expect(client.baseURL).toBe("https://custom.api/v1");
  });

  it("registers x402 EVM scheme", async () => {
    const { createLLMClient } = await import("../src/client.js");
    createLLMClient(TEST_PRIVATE_KEY);

    expect(mockRegisterExactEvmScheme).toHaveBeenCalledOnce();
  });

  it("wraps fetch with x402 payment", async () => {
    const { createLLMClient } = await import("../src/client.js");
    createLLMClient(TEST_PRIVATE_KEY);

    expect(mockWrapFetchWithPayment).toHaveBeenCalledOnce();
  });
});
