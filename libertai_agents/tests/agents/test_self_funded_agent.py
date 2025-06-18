import asyncio
import binascii
from unittest.mock import AsyncMock, patch

import pytest
from coinbase_agentkit import erc20_action_provider

from libertai_agents.agents.self_funded.agent import SelfFundedAgent
from libertai_agents.agents.self_funded.interfaces import SelfFundedAgentConfig
from libertai_agents.models import get_model
from tests.utils.models import get_hf_token, get_libertai_api_key, get_random_model_id


def test_self_funded_invalid_private_key():
    config = SelfFundedAgentConfig(private_key="invalid_private_key")
    with pytest.raises(binascii.Error):
        _agent = SelfFundedAgent(
            autonomous_config=config,
            model=get_model(get_random_model_id(), get_hf_token()),
            api_key=get_libertai_api_key()
        )


@patch.object(SelfFundedAgent, "survival_reflexion", new_callable=AsyncMock)
async def test_self_funded_scheduler(mock_survival_reflexion, eth_private_key):
    config = SelfFundedAgentConfig(
        private_key=eth_private_key,
        compute_think_unit="seconds",
        compute_think_interval=2,
    )
    agent = SelfFundedAgent(
        autonomous_config=config,
        model=get_model(get_random_model_id(), get_hf_token()),
        api_key=get_libertai_api_key(),
        tools=[],
    )

    # Starting the scheduler
    task = asyncio.create_task(agent._scheduler())
    # Function should be called directly and then after 2 seconds, adding an extra second margin
    await asyncio.sleep(3)
    task.cancel()

    assert mock_survival_reflexion.call_count >= 2


def test_self_funded_existing_agentkit_action_providers(eth_private_key):
    config = SelfFundedAgentConfig(
        private_key=eth_private_key,
        agentkit_additional_action_providers=[erc20_action_provider()],
    )

    with pytest.raises(ValueError):
        _agent = SelfFundedAgent(
            autonomous_config=config,
            model=get_model(get_random_model_id(), get_hf_token()),
            api_key=get_libertai_api_key(),
        )


def test_self_funded_no_fastapi(eth_private_key):
    config = SelfFundedAgentConfig(private_key=eth_private_key)
    with pytest.raises(ValueError):
        _agent = SelfFundedAgent(
            autonomous_config=config,
            model=get_model(get_random_model_id(), get_hf_token()),
            api_key=get_libertai_api_key(),
            expose_api=False,
        )


async def test_self_funded_survival(eth_private_key):
    config = SelfFundedAgentConfig(private_key=eth_private_key)
    agent = SelfFundedAgent(
        autonomous_config=config,
        model=get_model(get_random_model_id(), get_hf_token()),
        api_key=get_libertai_api_key(),
    )

    await agent.survival_reflexion()
    assert len(agent._logs_storage.keys()) == 1
