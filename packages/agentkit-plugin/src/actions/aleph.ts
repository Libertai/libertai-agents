import { z } from "zod";
import {
  customActionProvider,
  EvmWalletProvider,
  SuperfluidQueryActionProvider,
} from "@coinbase/agentkit";
import { createPublicClient, formatUnits, http, parseEther, encodeFunctionData } from "viem";
import { base } from "viem/chains";
import {
  ALEPH_ADDRESS,
  WETH_ADDRESS,
  UNISWAP_ROUTER,
  UNISWAP_ALEPH_POOL,
  uniswapV3PoolAbi,
  uniswapRouterAbi,
} from "./constants.js";

const balanceOfAbi = [
  {
    inputs: [{ name: "account", type: "address" }],
    name: "balanceOf",
    outputs: [{ name: "", type: "uint256" }],
    stateMutability: "view",
    type: "function",
  },
] as const;

export function createAlephActionProvider(rpcUrl?: string) {
  const publicClient = createPublicClient({
    chain: base,
    transport: http(rpcUrl),
  });

  return customActionProvider<EvmWalletProvider>([
    {
      name: "get_aleph_info",
      description:
        "Get your current ALEPH balance, hourly consumption rate, estimated hours of compute left, ETH balance, and ALEPH/ETH price. Use this to decide whether you need to buy more ALEPH.",
      schema: z.object({}),
      invoke: async (walletProvider: EvmWalletProvider, _args: unknown) => {
        try {
          const address = walletProvider.getAddress() as `0x${string}`;

          const sfQuery = new SuperfluidQueryActionProvider();
          const streamsResult = await sfQuery.queryStreams(walletProvider);

          let alephPerHour = 0;
          try {
            const jsonStr = streamsResult.replace("Current outflows are ", "");
            const outflows = JSON.parse(jsonStr) as Array<{
              currentFlowRate: string;
              token: { symbol: string };
              receiver: { id: string };
            }>;
            const alephOutflows = outflows.filter((o) =>
              o.token.symbol.toLowerCase().includes("aleph"),
            );
            const totalFlowRate = alephOutflows.reduce(
              (sum, o) => sum + BigInt(o.currentFlowRate),
              0n,
            );
            alephPerHour = parseFloat(formatUnits(totalFlowRate * 3600n, 18));
          } catch {
            // No outflows or parse error
          }

          const rawBalance = await publicClient.readContract({
            address: ALEPH_ADDRESS,
            abi: balanceOfAbi,
            functionName: "balanceOf",
            args: [address],
          });
          const alephBalance = parseFloat(formatUnits(rawBalance, 18));

          let hoursLeft = 1000000;
          if (alephPerHour > 0) {
            hoursLeft = Math.round(alephBalance / alephPerHour);
          }

          const ethBalanceWei = await publicClient.getBalance({ address });
          const ethBalance = parseFloat(formatUnits(ethBalanceWei, 18));

          const slot0 = await publicClient.readContract({
            address: UNISWAP_ALEPH_POOL,
            abi: uniswapV3PoolAbi,
            functionName: "slot0",
          });
          const sqrtPriceX96 = slot0[0];
          const price = Number(sqrtPriceX96) / 2 ** 96;
          const alephPerEth = price * price;

          return JSON.stringify({
            aleph_balance: Math.round(alephBalance * 1000) / 1000,
            aleph_consumed_per_hour: Math.round(alephPerHour * 1000) / 1000,
            hours_left_until_death: hoursLeft,
            eth_balance: Math.round(ethBalance * 10000) / 10000,
            aleph_per_eth: Math.round(alephPerEth * 100) / 100,
          });
        } catch (err) {
          return `Error getting ALEPH info: ${err instanceof Error ? err.message : String(err)}`;
        }
      },
    },
    {
      name: "swap_eth_to_aleph",
      description:
        "Swap ETH to ALEPH via Uniswap V3 to pay for your computing. Provide the amount of ETH to swap.",
      schema: z.object({
        ethAmount: z.string().describe("Amount of ETH to swap, e.g. '0.01'"),
      }),
      invoke: async (walletProvider: EvmWalletProvider, args: { ethAmount: string }) => {
        try {
          const amountInWei = parseEther(args.ethAmount);
          const address = walletProvider.getAddress() as `0x${string}`;

          const data = encodeFunctionData({
            abi: uniswapRouterAbi,
            functionName: "exactInputSingle",
            args: [
              {
                tokenIn: WETH_ADDRESS,
                tokenOut: ALEPH_ADDRESS,
                fee: 10000,
                recipient: address,
                amountIn: amountInWei,
                amountOutMinimum: 0n,
                sqrtPriceLimitX96: 0n,
              },
            ],
          });

          const txHash = await walletProvider.sendTransaction({
            to: UNISWAP_ROUTER,
            data,
            value: amountInWei,
          });

          return `Swap transaction sent. Hash: ${txHash}`;
        } catch (err) {
          return `Error swapping ETH to ALEPH: ${err instanceof Error ? err.message : String(err)}`;
        }
      },
    },
  ]);
}
