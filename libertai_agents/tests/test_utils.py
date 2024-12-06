from libertai_agents.interfaces.messages import Message, MessageRoleEnum
from libertai_agents.utils import find


def test_find():
    messages = [
        Message(role=MessageRoleEnum.system, content="You are a helpful assistant"),
        Message(
            role=MessageRoleEnum.user, content="What's the weather in Paris tomorrow?"
        ),
    ]
    user_message = find(lambda message: message.role == "user", messages)
    assert user_message == messages[1]


def test_find_inexistant():
    messages = [
        Message(role=MessageRoleEnum.system, content="You are a helpful assistant"),
        Message(
            role=MessageRoleEnum.user, content="What's the weather in Paris tomorrow?"
        ),
    ]
    tool_message = find(lambda message: message.role == MessageRoleEnum.tool, messages)
    assert tool_message is None
