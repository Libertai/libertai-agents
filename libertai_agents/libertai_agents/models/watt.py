import json
import random
import string
import re

from libertai_agents.interfaces.messages import ToolCallFunction
from libertai_agents.models.base import Model, ModelId

from libertai_agents.interfaces.messages import (
    Message,
    ToolCallFunction,
)
from libertai_agents.interfaces.tools import Tool

from jinja2 import TemplateError

class WattModel(Model):
    chat_template = """{{ '<|begin_of_text|>' }}{% if messages[0]['role'] == 'system' %}{% set loop_messages = messages[1:] %}{% set system_message = messages[0]['content'] %}{% else %}{% set loop_messages = messages %}{% endif %}{% if system_message is defined %}{{ '<|start_header_id|>system<|end_header_id|>\n\n' + system_message + '<|eot_id|>' }}{% endif %}{% for message in loop_messages %}{% set content = message['content'] %}{% if message['role'] == 'user' %}{{ '<|start_header_id|>user<|end_header_id|>\n\n' + content + '<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n' }}{% elif message['role'] == 'assistant' %}{% if message['tool_calls'] %}{{ tool_calls}} {% endif %}{% if message['content'] %}{{ content }} {% endif %}{{ '<|eot_id|>' }}{% elif message['role'] == 'tool' %}<|start_header_id|>tool<|end_header_id|>\n\n{{ content + '<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n' }}{% else %}{% endif %}{% endfor %}"""
    def __init__(self, model_id: ModelId, vm_url: str, context_length: int):
        super().__init__(
            model_id=model_id,
            vm_url=vm_url,
            context_length=context_length,
        )

    @staticmethod
    def extract_tool_calls_from_response(response: str) -> list[ToolCallFunction]:
        try:
            tool_calls = json.loads(response)
            return [ToolCallFunction(**call, content=call) for call in tool_calls]
        except Exception:
            try:
                tool_calls = re.findall(r"<tool_call>\s*(.*)\s*</tool_call>", response)
                return [ToolCallFunction(**json.loads(call), content=call) for call in tool_calls]
            except Exception:
                return []

    def generate_tool_call_id(self) -> str:
        return "".join(
            random.choice(string.ascii_letters + string.digits) for _ in range(9)
        )