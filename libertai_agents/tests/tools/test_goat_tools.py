from eth_account.signers.local import LocalAccount
from goat_adapters.langchain import get_on_chain_tools
from goat_wallets.evm import send_eth
from goat_wallets.web3 import Web3EVMWalletClient
from web3 import Web3
from web3.middleware import SignAndSendRawMiddlewareBuilder

from libertai_agents.interfaces.tools import Tool


def test_goat_send_eth_tool() -> None:
    # https://github.com/goat-sdk/goat/blob/main/python/examples/langchain/web3/example.py
    w3 = Web3(Web3.HTTPProvider("https://eth.llamarpc.com"))
    account: LocalAccount = w3.eth.account.create()
    w3.eth.default_account = account.address  # Set the default account
    w3.middleware_onion.add(
        SignAndSendRawMiddlewareBuilder.build(account)
    )  # Add middleware

    goat_langchain_tools = get_on_chain_tools(
        wallet=Web3EVMWalletClient(w3),
        plugins=[
            send_eth(),
        ],
    )
    ltai_tools = [Tool.from_langchain(t) for t in goat_langchain_tools]
    send_eth_tool = next((t for t in ltai_tools if t.name == "send_ETH"), None)
    assert send_eth_tool is not None
    assert send_eth_tool.args_schema == {
        "type": "function",
        "function": {
            "name": "send_ETH",
            "description": "Send ETH to an address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "The address to send ETH to",
                    },
                    "amount": {
                        "type": "string",
                        "description": "The amount of ETH to send",
                    },
                },
                "required": ["to", "amount"],
            },
        },
    }
