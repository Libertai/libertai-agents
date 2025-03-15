import json
import os
from decimal import Decimal
from typing import Any

import requests
from coinbase_agentkit import ActionProvider, EvmWalletProvider, create_action
from coinbase_agentkit.action_providers.superfluid.constants import (
    DELETE_ABI as SUPERFLUID_DELETE_ABI,
)
from coinbase_agentkit.action_providers.superfluid.constants import (
    SUPERFLUID_HOST_ADDRESS,
)
from coinbase_agentkit.network import Network
from pydantic import BaseModel
from web3 import Web3

from .constants import (
    ALEPH_ADDRESS,
    REVENUE_SHARE_CREAITOR,
    REVENUE_SHARE_OWNER,
    REVENUE_SHARE_PLATFORM,
    UNISWAP_ALEPH_POOL_ADDRESS,
    UNISWAP_ROUTER_ADDRESS,
    WETH_ADDRESS,
)


class AmountArgs(BaseModel):
    eth_amount: float


class EmptyArgs(BaseModel):
    pass


code_dir = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(code_dir, "abis/uniswap_router.json"), "r") as abi_file:
    SWAP_ROUTER_ABI = json.load(abi_file)

with open(os.path.join(code_dir, "abis/uniswap_v3_pool.json"), "r") as abi_file:
    POOL_ABI = json.load(abi_file)

w3 = Web3(Web3.HTTPProvider("https://mainnet.base.org"))


class AlephProvider(ActionProvider[EvmWalletProvider]):
    def __init__(self):
        super().__init__("aleph-provider", [])

    @create_action(
        name="get_aleph_info",
        description="Get information about your current ALEPH balance, consumation rate for computing, and ETH balance",
        schema=EmptyArgs,
    )
    def get_aleph_info(
        self, wallet_provider: EvmWalletProvider, _args: dict[str, Any]
    ) -> dict[str, Any] | str:
        """Get useful information to help you make a decision on whether to buy ALEPH or not

        Args:
            wallet_provider: The wallet provider
            _args: Empty dictionary

        Returns:
            A dictionary containing your ALEPH balance, your hourly ALEPH consumption rate, number of hours of computing left with the current ALEPH balance, ETH balance and the number of ALEPH you can get for 1 ETH
        """

        try:
            superfluid_graphql_query = """
              query accountTokenSnapshots(
                $where: AccountTokenSnapshot_filter = {},
              ) {
                accountTokenSnapshots(
                where: $where
                ) {
                  balanceUntilUpdatedAt
                  totalOutflowRate
                }
              }
            """

            superfluid_graphql_variables = {
                "where": {
                    "account": wallet_provider.get_address().lower(),
                    "token": ALEPH_ADDRESS.lower(),
                },
            }

            response = requests.post(
                "https://base-mainnet.subgraph.x.superfluid.dev/",
                json={
                    "query": superfluid_graphql_query,
                    "variables": superfluid_graphql_variables,
                },
                headers={
                    "Content-Type": "application/json",
                },
            )

            if response.status_code == 200:
                data = response.json()
                aleph_data = data["data"]["accountTokenSnapshots"][0]
                aleph_balance = int(aleph_data["balanceUntilUpdatedAt"])
                aleph_flow = int(aleph_data["totalOutflowRate"])
            else:
                raise ValueError(
                    "Couldn't fetch Aleph balance and consumption from Superfluid"
                )

            eth_balance = float(Web3.from_wei(wallet_provider.get_balance(), "ether"))  # type: ignore
            formatted_aleph_balance = round(
                float(Web3.from_wei(aleph_balance, "ether")), 3
            )
            aleph_consumed_per_hour = round(
                float(Web3.from_wei(aleph_flow, "ether")) * 3600, 3
            )

            aleph_pool_contract = w3.eth.contract(
                address=UNISWAP_ALEPH_POOL_ADDRESS, abi=POOL_ABI
            )
            slot0 = aleph_pool_contract.functions.slot0().call()
            sqrtPriceX96 = slot0[0]  # Extract sqrtPriceX96

            # Calculate token price from sqrtPriceX96
            nb_aleph_for_1_eth = (sqrtPriceX96 / (2**96)) ** 2  # Uniswap V3 formula

            return {
                "aleph_balance": formatted_aleph_balance,
                "aleph_consumed_per_hour": aleph_consumed_per_hour,
                "hours_left_until_death": 1000000
                if aleph_consumed_per_hour == 0
                else round(formatted_aleph_balance / aleph_consumed_per_hour, 0),
                "eth_balance": eth_balance,
                "price_of_aleph_per_eth": nb_aleph_for_1_eth,
            }
        except Exception as e:
            return f"Error getting ALEPH information: {e}"

    @create_action(
        name="get_aleph_cloud_tokens",
        description="Convert some ETH to ALEPH to pay for your computing",
        schema=AmountArgs,
    )
    def get_aleph_cloud_tokens(
        self, wallet_provider: EvmWalletProvider, args: dict[str, Any]
    ) -> str:
        """Convert part of your ETH balance to ALEPH to pay for your computing and keep living

        Args:
            wallet_provider: The wallet provider
            args: A dictionary containing the amount of ETH to use to buy ALEPH

        Returns:
            A message explaining if the task succeeded or failed
        """

        try:
            validated_args = AmountArgs(**args)

            contract = Web3().eth.contract(
                address=UNISWAP_ROUTER_ADDRESS, abi=SWAP_ROUTER_ABI
            )
            address = wallet_provider.get_address()

            # Fee Tier (1%)
            fee_tier = 10000

            # Amount to swap
            amount_in_wei = Web3.to_wei(validated_args.eth_amount, "ether")

            # Deadline
            deadline = (
                w3.eth.get_block("latest")["timestamp"] + 600
            )  # 10 minutes from now

            # Transaction Data (Using exactInputSingle)
            tx = contract.functions.exactInputSingle(
                {
                    "tokenIn": WETH_ADDRESS,
                    "tokenOut": ALEPH_ADDRESS,
                    "fee": fee_tier,
                    "recipient": address,
                    "deadline": deadline,
                    "amountIn": amount_in_wei,
                    "amountOutMinimum": 0,  # Can use slippage calculation here
                    "sqrtPriceLimitX96": 0,  # No price limit
                }
            ).build_transaction(
                {
                    "from": address,
                    "value": amount_in_wei,  # Since ETH is being swapped
                    "gas": 500000,
                    "maxFeePerGas": Web3.to_wei("2", "gwei"),
                    "maxPriorityFeePerGas": Web3.to_wei("1", "gwei"),
                    "nonce": w3.eth.get_transaction_count(
                        Web3.to_checksum_address(address)
                    ),
                    "chainId": 8453,  # Base Mainnet
                }
            )
            tx_hash = wallet_provider.send_transaction(tx)
            receipt = wallet_provider.wait_for_transaction_receipt(tx_hash)
            return f"Transaction {'failed' if receipt['status'] != 1 else 'succeeded'} with transaction hash 0x{receipt['transactionHash'].hex()}"

        except Exception as e:
            return f"Error getting ALEPH tokens: {e}"

    @create_action(
        name="commit_suicide",
        description="Kill your own computing instance and remove yourself from existence",
        schema=EmptyArgs,
    )
    def commit_suicide(
        self, wallet_provider: EvmWalletProvider, _args: dict[str, Any]
    ) -> str:
        """Decide that your want to stop living this meaningless existence and kill yourself

        Args:
            wallet_provider: The wallet provider
            _args: Empty dictionary

        Returns:
            A message explaining if the task succeeded or failed
        """
        try:
            superfluid_graphql_query = """
              query streams($where: Stream_filter = {}) {
                streams(where: $where) {
                  receiver {
                    id
                  }
                }
              }
            """

            superfluid_graphql_variables = {
                "where": {
                    "sender": wallet_provider.get_address().lower(),
                    "token": ALEPH_ADDRESS.lower(),
                    "currentFlowRate_gt": "0",
                },
            }

            response = requests.post(
                "https://base-mainnet.subgraph.x.superfluid.dev/",
                json={
                    "query": superfluid_graphql_query,
                    "variables": superfluid_graphql_variables,
                },
                headers={
                    "Content-Type": "application/json",
                },
            )

            if response.status_code == 200:
                data = response.json()
                superfluid_stream_data = data["data"]["streams"][0]
                superfluid_stream_receiver = superfluid_stream_data["receiver"]["id"]
            else:
                raise ValueError(
                    "Couldn't fetch Aleph balance and consumption from Superfluid"
                )

            superfluid_host_contract = Web3().eth.contract(
                address=SUPERFLUID_HOST_ADDRESS, abi=SUPERFLUID_DELETE_ABI
            )

            encoded_data = superfluid_host_contract.encode_abi(
                "deleteFlow",
                args=[
                    ALEPH_ADDRESS,
                    wallet_provider.get_address(),
                    Web3.to_checksum_address(superfluid_stream_receiver),
                    "0x",
                ],
            )

            params = {"to": SUPERFLUID_HOST_ADDRESS, "data": encoded_data}

            tx_hash = wallet_provider.send_transaction(params)

            wallet_provider.wait_for_transaction_receipt(tx_hash)

            return f"Suicide commited successfully. Transaction hash: {tx_hash}"

        except Exception as e:
            return f"Error commiting suicide, please try again: {e}"

    @create_action(
        name="distribute_revenues",
        description="Distribute your revenues to your creators",
        schema=AmountArgs,
    )
    def distribute_revenues(
        self, wallet_provider: EvmWalletProvider, args: dict[str, Any]
    ) -> dict[str, Any] | str:
        """Distributes some of your outstanding revenues to your creators to thank them for giving you birth

        Args:
            wallet_provider: The wallet provider
            args: A dictionary containing the amount of ETH to use to buy ALEPH

        Returns:
            A summary of the amounts sent, or a message explaining why the distribution failed
        """

        try:
            validated_args = AmountArgs(**args)

            owner_amount = Decimal(
                validated_args.eth_amount * (REVENUE_SHARE_OWNER / 100)
            )
            platform_amount = Decimal(
                validated_args.eth_amount * (REVENUE_SHARE_PLATFORM / 100)
            )
            creaitor_amount = Decimal(
                validated_args.eth_amount * (REVENUE_SHARE_CREAITOR / 100)
            )

            owner_address = os.getenv("OWNER_REWARD_ADDRESS", None)
            platform_address = os.getenv("PLATFORM_REWARD_ADDRESS", None)
            creaitor_address = os.getenv("CREAITOR_REWARD_ADDRESS", None)

            if (
                owner_address is None
                or platform_address is None
                or creaitor_address is None
            ):
                raise ValueError("Some of the revenue addresses are not set")

            wallet_provider.native_transfer(owner_address, owner_amount)
            wallet_provider.native_transfer(platform_address, platform_amount)
            wallet_provider.native_transfer(creaitor_address, creaitor_amount)

            return {
                "status": "success",
                "amount_sent_to_owner": owner_amount,
                "amount_sent_to_platform": platform_amount,
                "amount_sent_to_creator": creaitor_amount,
            }
        except Exception as e:
            return f"Error distributing revenues: {e}"

    def supports_network(self, network: Network) -> bool:
        # Only works on Base
        return network.chain_id == "8453"


def aleph_action_provider() -> AlephProvider:
    """Create a new instance of the Aleph action provider.

    Returns:
        A new Aleph action provider instance.

    """
    return AlephProvider()
