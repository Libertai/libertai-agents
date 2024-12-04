from typing import Callable, Any, TYPE_CHECKING

from pydantic.v1 import BaseModel
from transformers.utils import get_json_schema
from transformers.utils.chat_template_utils import _convert_type_hints_to_json_schema

if TYPE_CHECKING:
    # Importing only for type hinting purposes.
    from langchain_core.tools import BaseTool


class Tool(BaseModel):
    name: str
    function: Callable[..., Any]
    args_schema: dict

    @classmethod
    def from_function(cls, function: Callable[..., Any]):
        return cls(
            name=function.__name__,
            function=function,
            args_schema=get_json_schema(function),
        )

    @classmethod
    def from_langchain(cls, langchain_tool: "BaseTool"):
        try:
            from langchain_core.tools import StructuredTool
        except ImportError:
            raise RuntimeError(
                "langchain_core is required for this functionality. Install with: libertai-agents[langchain]"
            )

        if isinstance(langchain_tool, StructuredTool):
            # TODO: handle this case
            raise NotImplementedError("Langchain StructuredTool aren't supported yet")

        # Extracting function parameters to JSON schema
        function_parameters = _convert_type_hints_to_json_schema(langchain_tool._run)
        # Removing langchain-specific parameters
        function_parameters["properties"].pop("run_manager", None)
        function_parameters["properties"].pop("return", None)

        return cls(
            name=langchain_tool.name,
            function=langchain_tool._run,
            args_schema={
                "type": "function",
                "function": {
                    "name": langchain_tool.name,
                    "description": langchain_tool.description,
                    "parameters": function_parameters,
                },
            },
        )
