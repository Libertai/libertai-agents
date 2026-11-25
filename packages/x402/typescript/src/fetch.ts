import type { PaymentPolicy } from "@x402/core/client";
import { ExactEvmScheme, UptoEvmScheme } from "@x402/evm";
import {
  wrapFetchWithPayment as wrapFetchWithX402,
  x402Client,
} from "@x402/fetch";
import type { Hex } from "viem";
import { privateKeyToAccount } from "viem/accounts";

export const BASE_NETWORK = "eip155:8453";

export const LIBERTAI_API_ORIGIN = "https://api.libertai.io";
/** LibertAI's payment wallet, the `payTo` of every LibertAI API payment. */
export const LIBERTAI_PAY_TO = "0x48E5A3e497D0C092D5B0Ba22B5A86ADA94227DFa";
/** USDC on Base, the only token the default limits allow. */
export const BASE_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";
/** 5 USDC in atomic units (6 decimals). */
export const DEFAULT_MAX_AMOUNT = 5_000_000n;
export const DEFAULT_MAX_TIMEOUT_SECONDS = 86400;

/** Omitted options use the LibertAI defaults; `null` disables that check. */
export interface PaymentOptions {
  /** Origins allowed to request a payment and to receive a signed one. Default: `[LIBERTAI_API_ORIGIN]`. */
  allowedOrigins?: string[] | null;
  /** Recipient addresses allowed as `payTo` (case-insensitive). Default: `[LIBERTAI_PAY_TO]`. */
  allowedPayTo?: string[] | null;
  /** Token contracts allowed as `asset` (case-insensitive). Default: `[BASE_USDC]`. */
  allowedAssets?: string[] | null;
  /** Max atomic USDC units (6 decimals) a single payment may authorize. Default: `DEFAULT_MAX_AMOUNT`. */
  maxAmount?: string | bigint | null;
  /** Max `maxTimeoutSeconds` (signature validity) a payment may have. Default: `DEFAULT_MAX_TIMEOUT_SECONDS`. */
  maxTimeoutSeconds?: number | null;
}

function withDefault<T>(value: T | null | undefined, fallback: T): T | null {
  return value === undefined ? fallback : value;
}

export function createSpendingPolicy(
  options: PaymentOptions = {},
): PaymentPolicy {
  const rawMaxAmount = withDefault(options.maxAmount, DEFAULT_MAX_AMOUNT);
  const maxAmount = rawMaxAmount === null ? null : BigInt(rawMaxAmount);
  const rawAllowedPayTo = withDefault(options.allowedPayTo, [LIBERTAI_PAY_TO]);
  const allowedPayTo =
    rawAllowedPayTo === null
      ? null
      : rawAllowedPayTo.map((a) => a.toLowerCase());
  const rawAllowedAssets = withDefault(options.allowedAssets, [BASE_USDC]);
  const allowedAssets =
    rawAllowedAssets === null
      ? null
      : rawAllowedAssets.map((a) => a.toLowerCase());
  const maxTimeoutSeconds = withDefault(
    options.maxTimeoutSeconds,
    DEFAULT_MAX_TIMEOUT_SECONDS,
  );

  return (_version, requirements) => {
    const allowed = requirements.filter(
      (r) =>
        (maxAmount === null || BigInt(r.amount) <= maxAmount) &&
        (allowedPayTo === null ||
          allowedPayTo.includes(r.payTo.toLowerCase())) &&
        (allowedAssets === null ||
          allowedAssets.includes(r.asset.toLowerCase())) &&
        (maxTimeoutSeconds === null ||
          r.maxTimeoutSeconds <= maxTimeoutSeconds),
    );
    if (allowed.length === 0) {
      const offered = requirements
        .map(
          (r) =>
            `${r.amount} of ${r.asset} to ${r.payTo} (timeout ${r.maxTimeoutSeconds}s)`,
        )
        .join(", ");
      throw new Error(
        `x402: no payment option within limits (maxAmount=${maxAmount ?? "none"}, allowedPayTo=${allowedPayTo?.join(",") ?? "any"}, allowedAssets=${allowedAssets?.join(",") ?? "any"}, maxTimeoutSeconds=${maxTimeoutSeconds ?? "none"}); offered: ${offered}`,
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
  // The SDK's default spend controls cap every payment at $1; limits are only the spending policy's.
  const client = new x402Client()
    .register(BASE_NETWORK, new ExactEvmScheme(account))
    .register(BASE_NETWORK, new UptoEvmScheme(account))
    .setSpendControls(false)
    .registerPolicy(createSpendingPolicy(options));

  const allowedOrigins = withDefault(options.allowedOrigins, [
    LIBERTAI_API_ORIGIN,
  ])?.map((o) => new URL(o).origin);
  const isAllowedOrigin = (url: string) =>
    allowedOrigins == null || allowedOrigins.includes(new URL(url).origin);

  // "Bearer x402" is a placeholder API key (the OpenAI SDK requires one) and must never reach the server.
  // globalThis.fetch is looked up per call so it can be replaced after wrapping.
  // Every request the SDK sends goes through here, so origin checks cover its retries too.
  const baseFetch: typeof fetch = async (input, init) => {
    let req = new Request(input, init);
    if (req.headers.get("Authorization") === "Bearer x402") {
      req.headers.delete("Authorization");
    }
    if (req.headers.has("PAYMENT-SIGNATURE")) {
      if (!isAllowedOrigin(req.url)) {
        throw new Error(
          `x402: refusing to send a payment to non-allowed origin ${new URL(req.url).origin}`,
        );
      }
      // A redirect would carry the signed payment to wherever the server points.
      req = new Request(req, { redirect: "manual" });
    }
    const response = await globalThis.fetch(req);
    if (response.status === 402) {
      const url = response.url || req.url;
      if (!isAllowedOrigin(url)) {
        response.body?.cancel().catch(() => {});
        throw new Error(
          `x402: refusing to pay a 402 from non-allowed origin ${new URL(url).origin}`,
        );
      }
    }
    return response;
  };

  return wrapFetchWithX402(baseFetch, client) as typeof fetch;
}
