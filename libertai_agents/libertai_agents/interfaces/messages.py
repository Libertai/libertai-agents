from typing import Optional

from pydantic import BaseModel


class ToolCallFunction(BaseModel):
    name: str
    arguments: dict


class MessageToolCall(BaseModel):
    type: str
    id: Optional[str] = None
    function: ToolCallFunction


class Message(BaseModel):
    role: str
    content: Optional[str] = None


class ToolCallMessage(Message):
    tool_calls: list[MessageToolCall]


class ToolResponseMessage(Message):
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
