import type { PaymentPolicy } from "@x402/core/client";
import { ExactEvmScheme, UptoEvmScheme } from "@x402/evm";
import {
  wrapFetchWithPayment as wrapFetchWithX402,
  x402Client,
} from "@x402/fetch";
import type { Hex } from "viem";
import { privateKeyToAccount } from "viem/accounts";

export const BASE_NETWORK = "eip155:8453";

export interface PaymentOptions {
  /** Max atomic USDC units (6 decimals) a single payment may authorize. */
  maxAmount?: string | bigint;
  /** Recipient addresses allowed as `payTo` (case-insensitive). */
  allowedPayTo?: string[];
}

export function createSpendingPolicy(options: PaymentOptions): PaymentPolicy {
  const maxAmount =
    options.maxAmount === undefined ? undefined : BigInt(options.maxAmount);
  const allowedPayTo = options.allowedPayTo?.map((a) => a.toLowerCase());

  return (_version, requirements) => {
    const allowed = requirements.filter(
      (r) =>
        (maxAmount === undefined || BigInt(r.amount) <= maxAmount) &&
        (allowedPayTo === undefined ||
          allowedPayTo.includes(r.payTo.toLowerCase())),
    );
    if (allowed.length === 0) {
      const offered = requirements
        .map((r) => `${r.amount} to ${r.payTo}`)
        .join(", ");
      throw new Error(
        `x402: no payment option within limits (maxAmount=${maxAmount ?? "none"}, allowedPayTo=${allowedPayTo?.join(",") ?? "any"}); offered: ${offered}`,
      );
    }
    return allowed;
  };
}

export function wrapFetchWithPayment(
  privateKey: Hex,
  options: PaymentOptions = {},
): typeof fetch {
  const account = privateKeyToAccount(privateKey);
  // The SDK's default spend controls cap every payment at $1; limits are only the ones set in options.
  const client = new x402Client()
    .register(BASE_NETWORK, new ExactEvmScheme(account))
    .register(BASE_NETWORK, new UptoEvmScheme(account))
    .setSpendControls(false);
  if (options.maxAmount !== undefined || options.allowedPayTo !== undefined) {
    client.registerPolicy(createSpendingPolicy(options));
  }

  // "Bearer x402" is a placeholder API key (the OpenAI SDK requires one) and must never reach the server.
  // globalThis.fetch is looked up per call so it can be replaced after wrapping.
  const baseFetch: typeof fetch = (input, init) => {
    const req = new Request(input, init);
    if (req.headers.get("Authorization") === "Bearer x402") {
      req.headers.delete("Authorization");
    }
    return globalThis.fetch(req);
  };

  return wrapFetchWithX402(baseFetch, client) as typeof fetch;
}
