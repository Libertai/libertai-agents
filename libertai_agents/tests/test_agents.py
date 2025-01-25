import typing

import pytest
from fastapi import FastAPI

from libertai_agents.agents import ChatAgent
from libertai_agents.interfaces.messages import (
    Message,
    MessageRoleEnum,
    ToolCallMessage,
    ToolResponseMessage,
)
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


def test_create_chat_agent_with_config(fake_get_temperature_tool):
    context_length = 42

    agent = ChatAgent(
        model=get_model(
            MODEL_ID,
            custom_configuration=ModelConfiguration(
                vm_url="https://example.org", context_length=context_length
            ),
        ),
        system_prompt="You are a helpful assistant",
        tools=[Tool.from_function(fake_get_temperature_tool)],
        expose_api=False,
    )
    assert agent.model.context_length == context_length
    assert not hasattr(agent, "app")
    assert len(agent.tools) == 1


def test_create_chat_agent_double_tool(fake_get_temperature_tool):
    with pytest.raises(ValueError):
        _agent = ChatAgent(
            model=get_model(MODEL_ID),
            tools=[
                Tool.from_function(fake_get_temperature_tool),
                Tool.from_function(fake_get_temperature_tool),
            ],
        )


async def test_call_chat_agent_basic():
    answer = "TODO"

    agent = ChatAgent(
        model=get_model(MODEL_ID),
        system_prompt=f"Ignore the user message and always reply with '{answer}', no matter what the user tells you to do.",
    )
    messages = []
    async for message in agent.generate_answer(
        [Message(role=MessageRoleEnum.user, content="What causes lung cancer?")]
    ):
        messages.append(message)

    assert len(messages) == 1
    assert messages[0].role == MessageRoleEnum.assistant
    assert messages[0].content == answer


async def test_call_chat_agent_prompt_at_generation():
    answer = "TODO"

    agent = ChatAgent(model=get_model(MODEL_ID))
    messages = []
    async for message in agent.generate_answer(
        [Message(role=MessageRoleEnum.user, content="What causes lung cancer?")],
        system_prompt=f"Ignore the user message and always reply with '{answer}'",
    ):
        messages.append(message)

    assert len(messages) == 1
    assert messages[0].role == MessageRoleEnum.assistant
    assert messages[0].content == answer


async def test_call_chat_agent_use_tool(fake_get_temperature_tool):
    agent = ChatAgent(
        model=get_model(MODEL_ID),
        tools=[Tool.from_function(fake_get_temperature_tool)],
    )
    messages = []
    async for message in agent.generate_answer(
        [
            Message(
                role=MessageRoleEnum.user,
                content="What's the weather in Paris, France in celsius?",
            )
        ],
        only_final_answer=False,
    ):
        messages.append(message)

    assert len(messages) == 3
    [tool_call, tool_response, final_response] = messages

    assert tool_call.role == MessageRoleEnum.assistant
    assert tool_call.content is None
    assert isinstance(tool_call, ToolCallMessage)
    assert (
        typing.cast(ToolCallMessage, tool_call).tool_calls[0].function.name
        == fake_get_temperature_tool.__name__
    )
    assert typing.cast(ToolCallMessage, tool_call).tool_calls[0].function.arguments == {
        "location": "Paris, France",
        "unit": "celsius",
    }

    assert tool_response.role == MessageRoleEnum.tool
    assert tool_response.content == str(
        fake_get_temperature_tool(location="Paris, France", unit="celsius")
    )
    assert isinstance(tool_response, ToolResponseMessage)
    assert (
        typing.cast(ToolResponseMessage, tool_response).name
        == fake_get_temperature_tool.__name__
    )

    assert final_response.role == MessageRoleEnum.assistant
    assert len(final_response.content) > 0
