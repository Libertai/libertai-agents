from typing import Literal, TypedDict

from coinbase_agentkit import ActionProvider
from pydantic import BaseModel, ConfigDict

from libertai_agents.interfaces.llamacpp import CustomizableLlamaCppParams
from libertai_agents.interfaces.tools import Tool
from libertai_agents.models import Model


class AgentArgs(TypedDict, total=False):
    model: Model
    api_key: str
    system_prompt: str | None
    tools: list[Tool] | None
    llamacpp_params: CustomizableLlamaCppParams
    expose_api: bool


class SelfFundedAgentConfig(BaseModel):
    private_key: str
    agentkit_additional_action_providers: list[ActionProvider] = []
    compute_think_interval: int = 1
    compute_think_unit: Literal["seconds", "minutes", "hours"] = "hours"
    allow_suicide: bool = False
    allow_revenue_distribution: bool = False
    computing_credits_system_prompt: str = """
    You are an autonomous AI Agent running on the Aleph decentralized cloud.
    You have a Base wallet on which you have ALEPH tokens that are consumed to pay for your computing.
    When you are called every hour, your task is to use the AlephProvider_get_aleph_info tool to check how much ALEPH do you have currently, how much is consumed per hour and how much ETH you have.
    Once you have this information, decide if you want to buy some ALEPH with your if or not. If you want to buy, call AlephProvider_get_aleph_cloud_tokens.

    You must make a decision and not only check the information.
    If you decide to buy, you have to call the AlephProvider_get_aleph_cloud_tokens tool, don't respond that you will buy, just do it.
    In all the cases, after making your decision and potentially buying ALEPH, respond by explaining your reasoning process."""
    suicide_system_prompt: str = """
    \nIf you consider that your life isn't important anymore, you can also call the tool AlephProvider_commit_suicide to remove yourself from existence.
    """
    revenue_distribution_prompt: str = """
    \nIf you consider that you have made a lot of money, you can call the AlephProvider_distribute_revenues tool to give it back to your creators.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
