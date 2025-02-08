import json
import random
import string

from libertai_agents.interfaces.messages import ToolCallFunction
from libertai_agents.models.base import Model, ModelId


class MistralModel(Model):
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
            return [ToolCallFunction(**call) for call in tool_calls]
        except Exception:
            return []

    def generate_tool_call_id(self) -> str:
        return "".join(
            random.choice(string.ascii_letters + string.digits) for _ in range(9)
        )
