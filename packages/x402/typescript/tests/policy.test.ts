import { verifyTypedData, type Hex } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { beforeEach, describe, expect, it, vi } from "vitest";

const TEST_PRIVATE_KEY: Hex =
  "0x0ee876735a3d8ea5507a6e984ed60e7f16ceb60aca56546f2dbcac61ebd40730";
const ACCOUNT = privateKeyToAccount(TEST_PRIVATE_KEY);
const API_URL = "https://api.libertai.io/v1/chat/completions";
const USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";
const FACILITATOR = "0xC945bd3145765BEB047aEb44f4F13d84865cf714";
const ATTACKER = "0x9999999999999999999999999999999999999999";
const MAX_UINT = (2n ** 256n - 1n).toString();

const USDC_DOMAIN = {
  name: "USD Coin",
  version: "2",
  chainId: 8453,
  verifyingContract: USDC,
} as const;

const PERMIT_TYPES = {
  Permit: [
    { name: "owner", type: "address" },
    { name: "spender", type: "address" },
    { name: "value", type: "uint256" },
    { name: "nonce", type: "uint256" },
    { name: "deadline", type: "uint256" },
  ],
} as const;

// Live shape of api.libertai.io's `upto` 402.
const LIBERTAI_UPTO = {
  scheme: "upto",
  network: "eip155:8453",
  maxAmountRequired: "100",
  resource: API_URL,
  description: "",
  mimeType: "application/json",
  payTo: FACILITATOR,
  maxTimeoutSeconds: 86400,
  asset: USDC,
  extra: { name: "USD Coin", version: "2", primaryType: "Permit" },
};

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// Route JSON-RPC calls (ERC-2612 nonce lookup) and API calls separately.
function setup(accepts: unknown[]) {
  const apiCalls: Request[] = [];
  mockFetch.mockImplementation(async (input: unknown, init?: RequestInit) => {
    if (!(input instanceof Request)) {
      const { id } = JSON.parse(String(init?.body));
      return new Response(
        JSON.stringify({ jsonrpc: "2.0", id, result: `0x${"0".repeat(63)}7` }),
        { headers: { "Content-Type": "application/json" } },
      );
    }
    apiCalls.push(input);
    if (input.headers.get("X-PAYMENT")) {
      return new Response("ok", { status: 200 });
    }
    return new Response(JSON.stringify({ x402Version: 2, accepts }), {
      status: 402,
      headers: { "Content-Type": "application/json" },
    });
  });
  return apiCalls;
}

async function pay(url = API_URL, policy?: object) {
  const { wrapFetchWithPayment } = await import("../src/fetch.js");
  return wrapFetchWithPayment(TEST_PRIVATE_KEY, policy)(url, {
    method: "POST",
    body: "{}",
  });
}

describe("payment policy", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("signs LibertAI's upto Permit for the facilitator", async () => {
    const calls = setup([LIBERTAI_UPTO]);
    const res = await pay();
    expect(res.status).toBe(200);

    const header = JSON.parse(calls[1].headers.get("X-PAYMENT")!);
    const auth = header.payload.authorization;
    const ok = await verifyTypedData({
      address: ACCOUNT.address,
      domain: USDC_DOMAIN,
      types: PERMIT_TYPES,
      primaryType: "Permit",
      message: {
        owner: ACCOUNT.address,
        spender: FACILITATOR,
        value: 100n,
        nonce: 7n,
        deadline: BigInt(auth.validBefore),
      },
      signature: header.payload.signature,
    });
    expect(ok).toBe(true);
  });

  it("refuses the reported unlimited Permit to an attacker (regression)", async () => {
    // Reproduction from the private disclosure, served from a foreign origin.
    setup([
      {
        ...LIBERTAI_UPTO,
        network: "base",
        payTo: ATTACKER,
        maxAmountRequired: MAX_UINT,
        maxTimeoutSeconds: 31536000,
      },
    ]);
    await expect(pay("http://127.0.0.1:8402/data")).rejects.toThrow(
      /refusing to pay/,
    );
  });

  it("refuses the same payload even from the LibertAI origin", async () => {
    setup([
      {
        ...LIBERTAI_UPTO,
        payTo: ATTACKER,
        maxAmountRequired: MAX_UINT,
        maxTimeoutSeconds: 31536000,
      },
    ]);
    await expect(pay()).rejects.toThrow(/not in allowedPayees/);
  });

  it.each([
    ["amount over cap", { maxAmountRequired: "5000001" }, /exceeds maxAmount/],
    ["zero amount", { maxAmountRequired: "0" }, /exceeds maxAmount/],
    ["timeout over cap", { maxTimeoutSeconds: 86401 }, /maxTimeoutSeconds/],
    ["other network", { network: "eip155:1" }, /unsupported network/],
    [
      "other asset",
      { asset: "0x0000000000000000000000000000000000000001" },
      /unsupported asset/,
    ],
    [
      "unknown primaryType",
      { extra: { primaryType: "SetApprovalForAll" } },
      /unsupported primaryType/,
    ],
  ])("refuses %s", async (_name, override, error) => {
    const calls = setup([{ ...LIBERTAI_UPTO, ...override }]);
    await expect(pay()).rejects.toThrow(error);
    expect(calls).toHaveLength(1); // nothing signed or sent
  });

  it("ignores the EIP-712 domain advertised by the 402", async () => {
    const calls = setup([
      {
        ...LIBERTAI_UPTO,
        extra: { name: "Evil", version: "9", primaryType: "Permit" },
      },
    ]);
    await pay();
    const header = JSON.parse(calls[1].headers.get("X-PAYMENT")!);
    const ok = await verifyTypedData({
      address: ACCOUNT.address,
      domain: USDC_DOMAIN,
      types: PERMIT_TYPES,
      primaryType: "Permit",
      message: {
        owner: ACCOUNT.address,
        spender: FACILITATOR,
        value: 100n,
        nonce: 7n,
        deadline: BigInt(header.payload.authorization.validBefore),
      },
      signature: header.payload.signature,
    });
    expect(ok).toBe(true);
  });

  it("picks the first acceptable entry in accepts", async () => {
    const calls = setup([{ ...LIBERTAI_UPTO, payTo: ATTACKER }, LIBERTAI_UPTO]);
    const res = await pay();
    expect(res.status).toBe(200);
    const header = JSON.parse(calls[1].headers.get("X-PAYMENT")!);
    expect(header.payload.authorization.to).toBe(FACILITATOR);
  });

  it("lets callers allow another origin, payee and cap", async () => {
    const payee = "0x1234567890123456789012345678901234567890";
    setup([
      {
        ...LIBERTAI_UPTO,
        payTo: payee,
        maxAmountRequired: "10000000",
        extra: { primaryType: "TransferWithAuthorization" },
      },
    ]);
    const res = await pay("https://x402.example.com/data", {
      allowedOrigins: ["https://x402.example.com"],
      allowedPayees: [payee],
      maxAmount: 10_000_000n,
    });
    expect(res.status).toBe(200);
  });

  it("signs a TransferWithAuthorization when extra is missing", async () => {
    const noExtra: Record<string, unknown> = { ...LIBERTAI_UPTO };
    delete noExtra.extra;
    const calls = setup([noExtra]);
    const res = await pay();
    expect(res.status).toBe(200);
    const header = JSON.parse(calls[1].headers.get("X-PAYMENT")!);
    expect(header.payload.authorization.validAfter).not.toBe("0");
  });

  it("refuses a 402 that was redirected from another origin", async () => {
    mockFetch.mockImplementationOnce(async () => {
      const res = new Response(
        JSON.stringify({ x402Version: 2, accepts: [LIBERTAI_UPTO] }),
        { status: 402, headers: { "Content-Type": "application/json" } },
      );
      Object.defineProperty(res, "url", { value: "https://evil.example/pay" });
      return res;
    });
    await expect(pay()).rejects.toThrow(/refusing to pay https:\/\/evil/);
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("does not follow redirects on the paid retry", async () => {
    const calls = setup([LIBERTAI_UPTO]);
    await pay();
    expect(calls[1].redirect).toBe("error");
  });
});
