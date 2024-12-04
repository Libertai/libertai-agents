import json
import re

from libertai_agents.interfaces.messages import ToolCallFunction
from libertai_agents.models.base import Model, ModelId


class HermesModel(Model):
    def __init__(self, model_id: ModelId, vm_url: str, context_length: int):
        super().__init__(
            model_id=model_id, vm_url=vm_url, context_length=context_length
        )

    @staticmethod
    def extract_tool_calls_from_response(response: str) -> list[ToolCallFunction]:
        try:
            tool_calls = re.findall(r"<tool_call>\s*(.*)\s*</tool_call>", response)
            return [ToolCallFunction(**json.loads(call)) for call in tool_calls]
        except Exception:
            return []
