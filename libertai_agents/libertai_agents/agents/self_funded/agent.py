import asyncio
import datetime
import logging
import os
from logging import Logger

from coinbase_agentkit import (
    ActionProvider,
    AgentKit,
    AgentKitConfig,
    EthAccountWalletProvider,
    EthAccountWalletProviderConfig,
    erc20_action_provider,
    wallet_action_provider,
)
from coinbase_agentkit_langchain import get_langchain_tools
from dotenv import load_dotenv
from eth_account import Account
from starlette.middleware.cors import CORSMiddleware
from typing_extensions import Unpack

from libertai_agents.agents import Agent
from libertai_agents.interfaces.messages import (
    Message,
    ToolCallMessage,
    ToolResponseMessage,
)
from libertai_agents.interfaces.tools import Tool

from .interfaces import AgentArgs, AutonomousAgentConfig
from .provider import aleph_action_provider


class SelfFundedAgent:
    agent: Agent
    autonomous_config: AutonomousAgentConfig
    __logger: Logger
    __logs_storage: dict[str, str]

    def __init__(
        self, autonomous_config: AutonomousAgentConfig, **kwargs: Unpack[AgentArgs]
    ):
        load_dotenv()

        private_key = os.getenv("AGENT_WALLET_PRIVATE_KEY", None)
        if private_key is None:
            raise ValueError(
                "You must set the AGENT_WALLET_PRIVATE_KEY environment variable"
            )
        if not private_key.startswith("0x"):
            raise ValueError("Private key must start with 0x hex prefix")

        # Create Ethereum account from private key
        account = Account.from_key(private_key)

        # Initialize Ethereum Account Wallet Provider
        wallet_provider = EthAccountWalletProvider(
            config=EthAccountWalletProviderConfig(account=account, chain_id="8453")
        )

        # Initialize AgentKit
        agentkit_action_providers: list[ActionProvider] = [
            aleph_action_provider(),
            erc20_action_provider(),
            wallet_action_provider(),
        ]
        for action_provider in autonomous_config.agentkit_additional_action_providers:
            if action_provider.name in agentkit_action_providers:
                raise ValueError(
                    f"The AgentKit action provider '{action_provider.name}' is already present for the autonomous agent behavior, please remove it."
                )
            agentkit_action_providers.append(action_provider)

        agentkit = AgentKit(
            AgentKitConfig(
                wallet_provider=wallet_provider,
                action_providers=agentkit_action_providers,
            )
        )

        agentkit_tools = get_langchain_tools(agentkit)

        if kwargs["tools"] is None:
            kwargs["tools"] = []
        kwargs["tools"].extend([Tool.from_langchain(t) for t in agentkit_tools])  # type: ignore

        # Logging setup
        self.__logger = logging.getLogger("survival-reflexion")
        self.__logger.setLevel(logging.INFO)
        if not self.__logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - Survival reflexion - %(message)s",
                    "%Y-%m-%d %H:%M:%S",
                )
            )
            self.__logger.addHandler(handler)

        self.agent = Agent(**kwargs)  # type: ignore

        if self.agent.app is None:
            raise ValueError("Agent must expose a FastAPI app")

        self.agent.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Allows all origins
            allow_credentials=True,
            allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
            allow_headers=["*"],  # Allows all headers
        )

        self.autonomous_config = autonomous_config
        self.__logs_storage = {}

        @self.agent.app.on_event("startup")
        async def startup_event():
            asyncio.create_task(self.__scheduler())

        @self.agent.app.get("/survival-logs")
        async def get_survival_logs():
            return self.__logs_storage

    async def __scheduler(self):
        unit = self.autonomous_config.compute_think_unit
        unit_multiplier = 1
        if unit == "minutes":
            unit_multiplier = 60
        elif unit == "hours":
            unit_multiplier = 3600

        while True:
            await self.survival_reflexion()
            await asyncio.sleep(
                self.autonomous_config.compute_think_interval * unit_multiplier
            )

    async def survival_reflexion(self) -> None:
        """Call the agent to make it decide if it wants to buy $ALEPH for computing to survive or not"""
        base_prompt = self.autonomous_config.computing_credits_system_prompt
        prompt_with_suicide = (
            base_prompt
            if self.autonomous_config.allow_suicide is False
            else base_prompt + self.autonomous_config.suicide_system_prompt
        )
        prompt_with_revenue_distribution = (
            prompt_with_suicide
            if self.autonomous_config.allow_revenue_distribution is False
            else prompt_with_suicide
            + self.autonomous_config.revenue_distribution_prompt
        )
        prompt = prompt_with_revenue_distribution

        reflexion_logs: list[str] = []

        async for message in self.agent.generate_answer(
            messages=[
                Message(
                    role="user",
                    content="Perform your task",
                )
            ],
            system_prompt=prompt,
            only_final_answer=False,
        ):
            log = ""
            if isinstance(message, ToolCallMessage):
                for tool_call in message.tool_calls:
                    log = f"Tool {tool_call.function.name} called with arguments {tool_call.function.arguments}"
                    self.__logger.info(log)
            elif isinstance(message, ToolResponseMessage):
                log = f"Tool response: {message.content}"
                self.__logger.info(log)
            else:
                log = f"Agent response: {message.content}"
                self.__logger.info(log)
            reflexion_logs.append(log)
        self.__logs_storage[datetime.datetime.now().isoformat()] = "\n".join(
            reflexion_logs
        )
