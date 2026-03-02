import { type Abi } from "viem";

// --- Contract addresses (Base mainnet) ---
export const ALEPH_ADDRESS = "0xc0Fbc4967259786C743361a5885ef49380473dCF" as const;
export const WETH_ADDRESS = "0x4200000000000000000000000000000000000006" as const;
export const USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913" as const;
export const UNISWAP_ROUTER = "0x2626664c2603336E57B271c5C0b26F421741e481" as const;
export const UNISWAP_ALEPH_POOL = "0xe11C66b25F0e9a9eBEf1616B43424CC6E2168FC8" as const;

// --- Uniswap V3 pool ABI (slot0 only) ---
export const uniswapV3PoolAbi = [
  {
    inputs: [],
    name: "slot0",
    outputs: [
      { name: "sqrtPriceX96", type: "uint160" },
      { name: "tick", type: "int24" },
      { name: "observationIndex", type: "uint16" },
      { name: "observationCardinality", type: "uint16" },
      { name: "observationCardinalityNext", type: "uint16" },
      { name: "feeProtocol", type: "uint8" },
      { name: "unlocked", type: "bool" },
    ],
    stateMutability: "view",
    type: "function",
  },
] as const satisfies Abi;

// --- Uniswap V3 SwapRouter ABI (exactInputSingle only) ---
export const uniswapRouterAbi = [
  {
    inputs: [
      {
        components: [
          { name: "tokenIn", type: "address" },
          { name: "tokenOut", type: "address" },
          { name: "fee", type: "uint24" },
          { name: "recipient", type: "address" },
          { name: "amountIn", type: "uint256" },
          { name: "amountOutMinimum", type: "uint256" },
          { name: "sqrtPriceLimitX96", type: "uint160" },
        ],
        name: "params",
        type: "tuple",
      },
    ],
    name: "exactInputSingle",
    outputs: [{ name: "amountOut", type: "uint256" }],
    stateMutability: "payable",
    type: "function",
  },
] as const satisfies Abi;
