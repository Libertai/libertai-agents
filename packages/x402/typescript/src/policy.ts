import { getAddress, isAddress } from "viem";
import type { PaymentRequirements } from "./types.js";

export const BASE_NETWORK = "eip155:8453";
export const BASE_CHAIN_ID = 8453;

// USDC on Base. The EIP-712 domain is pinned here and never taken from a 402
// response: a server must not be able to choose which contract we sign for.
export const USDC_BASE = {
  address: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
  name: "USD Coin",
  version: "2",
} as const;

export const LIBERTAI_ORIGINS = ["https://api.libertai.io"];

// LibertAI's x402 facilitator (Permit spender for the `upto` scheme) and
// recipient wallet.
export const LIBERTAI_PAYEES = [
  "0xC945bd3145765BEB047aEb44f4F13d84865cf714",
  "0x48E5A3e497D0C092D5B0Ba22B5A86ADA94227DFa",
];

export const DEFAULT_MAX_AMOUNT = 5_000_000n; // 5 USDC per request
export const DEFAULT_MAX_TIMEOUT_SECONDS = 86_400; // 1 day

export interface PaymentPolicy {
  /** Origins the wrapper may pay. Defaults to the LibertAI API. */
  allowedOrigins?: string[];
  /** Addresses that may receive a payment or a Permit. Defaults to LibertAI's. */
  allowedPayees?: string[];
  /** Maximum amount per request, in USDC atomic units (6 decimals). Defaults to 5 USDC. */
  maxAmount?: bigint | number | string;
  /** Maximum validity of a signature, in seconds. Defaults to 1 day. */
  maxTimeoutSeconds?: number;
}

export interface ResolvedPolicy {
  allowedOrigins: Set<string>;
  allowedPayees: Set<string>;
  maxAmount: bigint;
  maxTimeoutSeconds: number;
}

export function resolvePolicy(policy: PaymentPolicy = {}): ResolvedPolicy {
  return {
    allowedOrigins: new Set(
      (policy.allowedOrigins ?? LIBERTAI_ORIGINS).map((o) => new URL(o).origin),
    ),
    allowedPayees: new Set(
      (policy.allowedPayees ?? LIBERTAI_PAYEES).map((a) => getAddress(a)),
    ),
    maxAmount: BigInt(policy.maxAmount ?? DEFAULT_MAX_AMOUNT),
    maxTimeoutSeconds: policy.maxTimeoutSeconds ?? DEFAULT_MAX_TIMEOUT_SECONDS,
  };
}

export class PaymentRejectedError extends Error {
  constructor(message: string) {
    super(`x402: ${message}`);
    this.name = "PaymentRejectedError";
  }
}

export function checkOrigin(url: string, policy: ResolvedPolicy): void {
  const origin = new URL(url).origin;
  if (!policy.allowedOrigins.has(origin)) {
    throw new PaymentRejectedError(
      `refusing to pay ${origin}: not in allowedOrigins`,
    );
  }
}

/** Returns the reason a requirement is rejected, or null if it may be signed. */
export function rejectReason(
  req: PaymentRequirements,
  policy: ResolvedPolicy,
): string | null {
  if (req.network !== BASE_NETWORK) {
    return `unsupported network ${req.network}`;
  }
  if (
    !isAddress(req.asset) ||
    getAddress(req.asset) !== getAddress(USDC_BASE.address)
  ) {
    return `unsupported asset ${req.asset}`;
  }
  const primaryType = req.extra?.primaryType ?? "TransferWithAuthorization";
  if (primaryType !== "TransferWithAuthorization" && primaryType !== "Permit") {
    return `unsupported primaryType ${primaryType}`;
  }
  if (
    !isAddress(req.payTo) ||
    !policy.allowedPayees.has(getAddress(req.payTo))
  ) {
    return `payee ${req.payTo} not in allowedPayees`;
  }
  let amount: bigint;
  try {
    amount = BigInt(req.maxAmountRequired);
  } catch {
    return `invalid amount ${req.maxAmountRequired}`;
  }
  if (amount <= 0n || amount > policy.maxAmount) {
    return `amount ${req.maxAmountRequired} exceeds maxAmount ${policy.maxAmount}`;
  }
  if (
    !Number.isInteger(req.maxTimeoutSeconds) ||
    req.maxTimeoutSeconds <= 0 ||
    req.maxTimeoutSeconds > policy.maxTimeoutSeconds
  ) {
    return `maxTimeoutSeconds ${req.maxTimeoutSeconds} exceeds ${policy.maxTimeoutSeconds}`;
  }
  return null;
}

export function selectRequirements(
  accepts: PaymentRequirements[],
  policy: ResolvedPolicy,
): PaymentRequirements {
  const reasons: string[] = [];
  for (const req of accepts) {
    const reason = rejectReason(req, policy);
    if (reason === null) return req;
    reasons.push(reason);
  }
  throw new PaymentRejectedError(
    `no acceptable payment requirements (${reasons.join("; ")})`,
  );
}
