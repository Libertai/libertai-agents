import { createPublicClient, http, type Hex } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { base } from "viem/chains";
import {
  checkOrigin,
  resolvePolicy,
  selectRequirements,
  type PaymentPolicy,
} from "./policy.js";
import { createPaymentHeader } from "./sign.js";
import type { PaymentRequirements } from "./types.js";

export function wrapFetchWithPayment(
  privateKey: Hex,
  policy?: PaymentPolicy,
): typeof fetch {
  const account = privateKeyToAccount(privateKey);
  const publicClient = createPublicClient({ chain: base, transport: http() });
  const resolved = resolvePolicy(policy);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return async (input: any, init?: any) => {
    const req = new Request(input, init);
    if (req.headers.get("Authorization") === "Bearer x402") {
      req.headers.delete("Authorization");
    }

    const response = await fetch(req);
    if (response.status !== 402) return response;

    const body = await response.json();
    const accepts: PaymentRequirements[] | undefined = body.accepts;
    if (!Array.isArray(accepts) || accepts.length === 0) {
      throw new Error("x402: 402 response missing accepts[0]");
    }

    // Check where the 402 actually came from (after redirects), not only
    // where we sent the request.
    checkOrigin(req.url, resolved);
    if (response.url && response.url !== req.url) {
      checkOrigin(response.url, resolved);
    }
    const requirements = selectRequirements(accepts, resolved);

    const paymentHeader = await createPaymentHeader(
      account,
      publicClient,
      requirements,
    );

    // Don't follow redirects with the signed payment attached: fetch would
    // forward X-PAYMENT to wherever the redirect points.
    const retryReq = new Request(input, { ...init, redirect: "error" });
    if (retryReq.headers.get("Authorization") === "Bearer x402") {
      retryReq.headers.delete("Authorization");
    }
    retryReq.headers.set("X-PAYMENT", paymentHeader);
    return fetch(retryReq);
  };
}
