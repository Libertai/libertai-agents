from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from coinbase_agentkit.wallet_providers.eth_account_wallet_provider import (
    EthAccountWalletProvider,
    EthAccountWalletProviderConfig,
)
from eth_account import Account

# USDC on Base mainnet
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
# USDC on Base Sepolia
USDC_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"

# Base chain IDs
BASE_MAINNET_CHAIN_ID = "8453"
BASE_SEPOLIA_CHAIN_ID = "84532"

ERC20_BALANCE_OF_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    }
]


@dataclass
class WalletInfo:
    address: str
    eth_balance: str
    usdc_balance: str
    chain_name: str


def create_agent_wallet(
    private_key: str,
    *,
    chain_id: str = BASE_MAINNET_CHAIN_ID,
    rpc_url: Optional[str] = None,
) -> EthAccountWalletProvider:
    """Create a wallet provider from a private key."""
    account = Account.from_key(private_key)
    config = EthAccountWalletProviderConfig(
        account=account,
        chain_id=chain_id,
        rpc_url=rpc_url,
    )
    return EthAccountWalletProvider(config)


def get_balances(wallet_provider: EthAccountWalletProvider) -> WalletInfo:
    """Get ETH and USDC balances for the wallet."""
    address = wallet_provider.get_address()
    network = wallet_provider.get_network()
    chain_id = network.chain_id if network else BASE_MAINNET_CHAIN_ID

    eth_balance = str(wallet_provider.get_balance())

    usdc_address = USDC_BASE if chain_id == BASE_MAINNET_CHAIN_ID else USDC_BASE_SEPOLIA

    try:
        usdc_raw = wallet_provider.read_contract(
            contract_address=usdc_address,
            abi=ERC20_BALANCE_OF_ABI,
            function_name="balanceOf",
            args=[address],
        )
        usdc_balance = str(int(usdc_raw) / 10**6)
    except Exception:
        usdc_balance = "0"

    chain_name = "Base" if chain_id == BASE_MAINNET_CHAIN_ID else "Base Sepolia"

    return WalletInfo(
        address=address,
        eth_balance=eth_balance,
        usdc_balance=usdc_balance,
        chain_name=chain_name,
    )
