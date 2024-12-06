from typing import TYPE_CHECKING, Any, Callable

from pydantic.json_schema import GenerateJsonSchema, JsonSchemaMode, JsonSchemaValue
from pydantic.v1 import BaseModel
from pydantic_core import CoreSchema
from transformers.utils import get_json_schema
from transformers.utils.chat_template_utils import _convert_type_hints_to_json_schema

if TYPE_CHECKING:
    # Importing only for type hinting purposes.
    from langchain_core.tools import BaseTool  # type: ignore


class GenerateToolPropertiesJsonSchema(GenerateJsonSchema):
    def generate(
        self, schema: CoreSchema, mode: JsonSchemaMode = "validation"
    ) -> JsonSchemaValue:
        json_schema = super().generate(schema, mode=mode)
        for key in json_schema["properties"].keys():
            json_schema["properties"][key].pop("title", None)
        json_schema.pop("title", None)
        return json_schema


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
            # Particular case
            structured_langchain_tool: StructuredTool = langchain_tool
            function_parameters = (
                structured_langchain_tool.args_schema.model_json_schema(
                    schema_generator=GenerateToolPropertiesJsonSchema
                )
            )

            if structured_langchain_tool.func is None:
                raise ValueError("Tool function is None, expected a Callable value")

            return cls(
                name=structured_langchain_tool.name,
                function=structured_langchain_tool.func,
                args_schema={
                    "type": "function",
                    "function": {
                        "name": structured_langchain_tool.name,
                        "description": structured_langchain_tool.description,
                        "parameters": function_parameters,
                    },
                },
            )

        # Extracting function parameters to JSON schema
        function_parameters = _convert_type_hints_to_json_schema(langchain_tool._run)
        # Removing langchain-specific parameters
        function_parameters["properties"].pop("run_manager", None)
        function_parameters["properties"].pop("return", None)

        # Extracting the description from the tool arguments if available
        for arg_name in function_parameters["properties"].keys():
            arg_data: dict[str, str] | None = langchain_tool.args.get(arg_name, None)
            if arg_data is None:
                continue
            arg_description = arg_data.get("description", None)
            if arg_description is None:
                continue
            function_parameters["properties"][arg_name]["description"] = arg_description

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
