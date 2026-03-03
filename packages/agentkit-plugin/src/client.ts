import OpenAI from "openai";
import { x402Client, wrapFetchWithPayment } from "@x402/fetch";
import { registerExactEvmScheme } from "@x402/evm/exact/client";
import { createWalletClient, http, type Hex } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { publicActions } from "viem";
import { base } from "viem/chains";

const DEFAULT_BASE_URL = "https://api.libertai.io/v1";

export interface LLMClientOptions {
  baseURL?: string;
}

export function createLLMClient(
  privateKey: Hex,
  options?: LLMClientOptions,
): OpenAI {
  const account = privateKeyToAccount(privateKey);
  const signer = createWalletClient({
    account,
    chain: base,
    transport: http(),
  }).extend(publicActions);

  const client = new x402Client();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  registerExactEvmScheme(client, { signer: signer as any });

  const fetchWithPayment = wrapFetchWithPayment(fetch, client);

  return new OpenAI({
    baseURL: options?.baseURL ?? DEFAULT_BASE_URL,
    apiKey: "x402",
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    fetch: fetchWithPayment as any,
  });
}
