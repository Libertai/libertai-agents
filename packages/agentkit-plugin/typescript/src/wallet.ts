import {
  createWalletClient,
  createPublicClient,
  http,
  type Account,
  type Chain,
  type Hex,
  type PublicClient,
  type Transport,
  type WalletClient,
} from "viem";
import { privateKeyToAccount, type PrivateKeyAccount } from "viem/accounts";
import { ViemWalletProvider } from "@coinbase/agentkit";

export interface AgentWallet {
  walletClient: WalletClient<Transport, Chain, Account>;
  publicClient: PublicClient<Transport, Chain>;
  provider: ViemWalletProvider;
  account: PrivateKeyAccount;
}

export async function createAgentWallet(
  privateKey: Hex,
  chain: Chain,
  rpcUrl?: string,
): Promise<AgentWallet> {
  const account = privateKeyToAccount(privateKey);

  const walletClient = createWalletClient({
    account,
    chain,
    transport: http(rpcUrl),
  });

  const publicClient = createPublicClient({
    chain,
    transport: http(rpcUrl),
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const provider = new ViemWalletProvider(walletClient as any);

  return { walletClient, publicClient, provider, account };
}
