import json
import re

from libertai_agents.interfaces import ToolCallFunction
from libertai_agents.models.base import Model


class HermesModel(Model):
    def __init__(self, model_id: str, vm_url: str):
        super().__init__(model_id, vm_url)

    @staticmethod
    def extract_tool_calls_from_response(response: str) -> list[ToolCallFunction]:
        tool_calls = re.findall("<tool_call>\s*(.*)\s*</tool_call>", response)
        return [ToolCallFunction(**json.loads(call)) for call in tool_calls]
