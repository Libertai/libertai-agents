from fastapi import FastAPI

from libertai_agents.agents import ChatAgent
from libertai_agents.interfaces.tools import Tool
from libertai_agents.models import get_model
from libertai_agents.models.base import ModelId
from libertai_agents.models.models import ModelConfiguration

MODEL_ID: ModelId = "NousResearch/Hermes-3-Llama-3.1-8B"


def test_create_chat_agent_minimal():
    agent = ChatAgent(model=get_model(MODEL_ID))

    assert len(agent.tools) == 0
    assert agent.model.model_id == MODEL_ID
    assert isinstance(agent.app, FastAPI)


def test_create_chat_agent_with_config(basic_function_for_tool):
    context_length = 42

    agent = ChatAgent(
        model=get_model(
            MODEL_ID,
            custom_configuration=ModelConfiguration(
                vm_url="https://example.org", context_length=context_length
            ),
        ),
        tools=[Tool.from_function(basic_function_for_tool)],
        expose_api=False,
    )
    assert agent.model.context_length == context_length
    assert not hasattr(agent, "app")
    assert len(agent.tools) == 1
