import type { EvmWalletProvider } from "@coinbase/agentkit";
import type { Hex } from "viem";
import { beforeEach, describe, expect, it, vi } from "vitest";

const TEST_PRIVATE_KEY: Hex =
  "0x0ee876735a3d8ea5507a6e984ed60e7f16ceb60aca56546f2dbcac61ebd40730";

const mockWrappedFetch = vi.fn();
const mockWrapFetchWithPayment = vi.fn(
  (..._args: unknown[]) => mockWrappedFetch,
);

vi.mock("@libertai/x402", () => ({
  wrapFetchWithPayment: (...args: unknown[]) =>
    mockWrapFetchWithPayment(...args),
}));

// AgentKit sends an analytics event on every action invocation.
const mockGlobalFetch = vi.fn(async () => new Response(null, { status: 200 }));
vi.stubGlobal("fetch", mockGlobalFetch);

const walletProvider = {
  getName: () => "test",
  getAddress: () => "0x0000000000000000000000000000000000000000",
  getNetwork: () => ({ protocolFamily: "evm", networkId: "base-mainnet" }),
} as unknown as EvmWalletProvider;

async function buyCredits(amount: number): Promise<string> {
  const { createAlephActionProvider } = await import("../src/actions/aleph.js");
  const provider = createAlephActionProvider(TEST_PRIVATE_KEY);
  const action = provider
    .getActions(walletProvider)
    .find((a) => a.name.endsWith("buy_credits"))!;
  return action.invoke({ amount });
}

describe("buy_credits", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockWrappedFetch.mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );
  });

  it.each([
    [10, 10_000_000n],
    [0.1234567, 123_457n],
  ])(
    "caps the payment at the purchase amount (%s USD)",
    async (amount, max) => {
      await buyCredits(amount);

      expect(mockWrapFetchWithPayment).toHaveBeenCalledWith(TEST_PRIVATE_KEY, {
        maxAmount: max,
      });
      expect(mockWrappedFetch).toHaveBeenCalledWith(
        "https://api.libertai.io/libertai/aleph-credits",
        expect.objectContaining({ method: "POST" }),
      );
    },
  );

  it("creates a payment fetch per purchase", async () => {
    await buyCredits(1);
    await buyCredits(2);

    expect(mockWrapFetchWithPayment).toHaveBeenCalledTimes(2);
  });
});
