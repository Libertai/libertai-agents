import { type PaymentOptions, wrapFetchWithPayment } from "@libertai/x402";
import OpenAI from "openai";
import type { Hex } from "viem";

const DEFAULT_BASE_URL = "https://api.libertai.io/v1";

export interface LLMClientOptions {
  baseURL?: string;
  /** Payment limits; `allowedOrigins` defaults to the `baseURL` origin, the rest to `@libertai/x402`'s defaults. */
  paymentOptions?: PaymentOptions;
}

export function createLLMClient(
  privateKey: Hex,
  options?: LLMClientOptions,
): OpenAI {
  const baseURL = options?.baseURL ?? DEFAULT_BASE_URL;
  const fetchWithPayment = wrapFetchWithPayment(privateKey, {
    allowedOrigins: [new URL(baseURL).origin],
    ...options?.paymentOptions,
  });
  return new OpenAI({
    baseURL,
    apiKey: "x402",
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    fetch: fetchWithPayment as any,
  });
}
