import {
  createWalletClient,
  createPublicClient,
  http,
  formatUnits,
  type Hex,
  type Chain,
} from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { erc20Abi } from "viem";
import { ViemWalletProvider } from "@coinbase/agentkit";
import { Attribution } from "ox/erc8021";

const BUILDER_CODE = "bc_kj26kx76";

// USDC on Base mainnet
const USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913" as const;
// USDC on Base Sepolia
const USDC_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7e" as const;

export interface WalletInfo {
  address: string;
  ethBalance: string;
  usdcBalance: string;
  chainName: string;
}

export async function createAgentWallet(privateKey: Hex, chain: Chain, rpcUrl?: string) {
  const account = privateKeyToAccount(privateKey);
  const dataSuffix = Attribution.toDataSuffix({ codes: [BUILDER_CODE] });

  const walletClient = createWalletClient({
    account,
    chain,
    transport: http(rpcUrl),
    dataSuffix,
  });

  const publicClient = createPublicClient({
    chain,
    transport: http(rpcUrl),
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const provider = new ViemWalletProvider(walletClient as any);

  const usdcAddress = chain.id === 8453 ? USDC_BASE : USDC_BASE_SEPOLIA;

  return { walletClient, publicClient, provider, account, usdcAddress };
}

export async function getBalances(
  wallet: Awaited<ReturnType<typeof createAgentWallet>>,
): Promise<WalletInfo> {
  const { publicClient, account, usdcAddress, walletClient } = wallet;

  const [ethBal, usdcBal] = await Promise.all([
    publicClient.getBalance({ address: account.address }),
    publicClient.readContract({
      address: usdcAddress,
      abi: erc20Abi,
      functionName: "balanceOf",
      args: [account.address],
    }),
  ]);

  return {
    address: account.address,
    ethBalance: formatUnits(ethBal, 18),
    usdcBalance: formatUnits(usdcBal as bigint, 6),
    chainName: walletClient.chain?.name ?? "unknown",
  };
}
