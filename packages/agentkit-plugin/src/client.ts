import OpenAI from "openai";
import {
  createPublicClient,
  http,
  getAddress,
  toHex,
  parseAbi,
  type Hex,
} from "viem";
import { privateKeyToAccount, type PrivateKeyAccount } from "viem/accounts";
import { base } from "viem/chains";

const DEFAULT_BASE_URL = "https://api.libertai.io/v1";

export interface LLMClientOptions {
  baseURL?: string;
}

interface PaymentRequirements {
  scheme: string;
  network: string;
  maxAmountRequired: string;
  resource: string;
  payTo: string;
  maxTimeoutSeconds: number;
  asset: string;
  extra: {
    name: string;
    version: string;
    primaryType?: string;
    [key: string]: unknown;
  };
}

async function createPaymentHeader(
  account: PrivateKeyAccount,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  publicClient: any,
  requirements: PaymentRequirements,
): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  const primaryType =
    requirements.extra.primaryType ?? "TransferWithAuthorization";

  const domain = {
    name: requirements.extra.name,
    version: requirements.extra.version,
    chainId: base.id,
    verifyingContract: getAddress(requirements.asset),
  };

  if (primaryType === "Permit") {
    const nonce = await publicClient.readContract({
      address: getAddress(requirements.asset) as `0x${string}`,
      abi: parseAbi(["function nonces(address) view returns (uint256)"]),
      functionName: "nonces",
      args: [getAddress(account.address)],
    });

    const deadline = BigInt(now + requirements.maxTimeoutSeconds);
    const permit = {
      owner: getAddress(account.address),
      spender: getAddress(requirements.payTo),
      value: BigInt(requirements.maxAmountRequired),
      nonce,
      deadline,
    };

    const signature = await account.signTypedData({
      domain,
      types: {
        Permit: [
          { name: "owner", type: "address" },
          { name: "spender", type: "address" },
          { name: "value", type: "uint256" },
          { name: "nonce", type: "uint256" },
          { name: "deadline", type: "uint256" },
        ],
      },
      primaryType: "Permit",
      message: permit,
    });

    return JSON.stringify({
      x402Version: 2,
      scheme: requirements.scheme,
      network: requirements.network,
      payload: {
        signature,
        authorization: {
          from: account.address,
          to: requirements.payTo,
          value: requirements.maxAmountRequired,
          validAfter: "0",
          validBefore: deadline.toString(),
          nonce: toHex(nonce, { size: 32 }),
        },
      },
    });
  }

  // TransferWithAuthorization (default)
  const nonce = toHex(crypto.getRandomValues(new Uint8Array(32)));
  const authorization = {
    from: getAddress(account.address),
    to: getAddress(requirements.payTo),
    value: BigInt(requirements.maxAmountRequired),
    validAfter: BigInt(now - 600),
    validBefore: BigInt(now + requirements.maxTimeoutSeconds),
    nonce,
  };

  const signature = await account.signTypedData({
    domain,
    types: {
      TransferWithAuthorization: [
        { name: "from", type: "address" },
        { name: "to", type: "address" },
        { name: "value", type: "uint256" },
        { name: "validAfter", type: "uint256" },
        { name: "validBefore", type: "uint256" },
        { name: "nonce", type: "bytes32" },
      ],
    },
    primaryType: "TransferWithAuthorization",
    message: authorization,
  });

  return JSON.stringify({
    x402Version: 2,
    scheme: requirements.scheme,
    network: requirements.network,
    payload: {
      signature,
      authorization: {
        from: account.address,
        to: requirements.payTo,
        value: requirements.maxAmountRequired,
        validAfter: (now - 600).toString(),
        validBefore: (now + requirements.maxTimeoutSeconds).toString(),
        nonce,
      },
    },
  });
}

export function createLLMClient(
  privateKey: Hex,
  options?: LLMClientOptions,
): OpenAI {
  const account = privateKeyToAccount(privateKey);
  const publicClient = createPublicClient({ chain: base, transport: http() });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fetchWithX402Payment = async (input: any, init?: any) => {
    const req = new Request(input, init);
    req.headers.delete("Authorization");

    const response = await fetch(req);
    if (response.status !== 402) return response;

    const body = await response.json();
    const requirements: PaymentRequirements = body.accepts?.[0];
    if (!requirements) {
      throw new Error("x402: 402 response missing accepts[0]");
    }

    const paymentHeader = await createPaymentHeader(
      account,
      publicClient,
      requirements,
    );

    const retryReq = new Request(input, init);
    retryReq.headers.delete("Authorization");
    retryReq.headers.set("X-PAYMENT", paymentHeader);
    return fetch(retryReq);
  };

  return new OpenAI({
    baseURL: options?.baseURL ?? DEFAULT_BASE_URL,
    apiKey: "x402",
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    fetch: fetchWithX402Payment as any,
  });
}
