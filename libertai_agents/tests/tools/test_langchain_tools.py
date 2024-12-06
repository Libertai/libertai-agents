from tempfile import TemporaryDirectory

from langchain_community.agent_toolkits import FileManagementToolkit, JsonToolkit
from langchain_community.agent_toolkits.openapi.toolkit import RequestsToolkit
from langchain_community.tools.json.tool import JsonSpec
from langchain_community.utilities.requests import TextRequestsWrapper

from libertai_agents.interfaces.tools import Tool
from libertai_agents.utils import find

# TODO: uncomment when https://huggingface.co/spaces/lysandre/hf-model-downloads/discussions/1 is merged
# def test_langchain_huggingface_hub_tool():
#     # https://python.langchain.com/docs/integrations/tools/huggingface_tools/
#     tool = load_huggingface_tool("lysandre/hf-model-downloads")
#
#     libertai_tool = Tool.from_langchain(tool)
#     assert libertai_tool.name == tool.name


def test_langchain_filesystem_tools():
    # https://python.langchain.com/docs/integrations/tools/filesystem/
    working_directory = TemporaryDirectory()
    toolkit = FileManagementToolkit(root_dir=str(working_directory.name))
    tools = toolkit.get_tools()

    libertai_tools = [Tool.from_langchain(t) for t in tools]

    copy_tool = find(lambda t: t.name == "copy_file", libertai_tools)
    assert copy_tool is not None
    assert copy_tool.args_schema == {
        "type": "function",
        "function": {
            "name": "copy_file",
            "description": "Create a copy of a file in a specified location",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_path": {
                        "type": "string",
                        "description": "Path of the file to copy",
                    },
                    "destination_path": {
                        "type": "string",
                        "description": "Path to save the copied file",
                    },
                },
                "required": ["source_path", "destination_path"],
            },
        },
    }


def test_langchain_json_tools():
    # https://python.langchain.com/docs/integrations/tools/json/
    json_spec = JsonSpec(dict_={}, max_value_length=4000)
    json_toolkit = JsonToolkit(spec=json_spec)
    tools = json_toolkit.get_tools()

    libertai_tools = [Tool.from_langchain(t) for t in tools]
    list_keys_tool = find(lambda t: t.name == "json_spec_list_keys", libertai_tools)
    get_value_tool = find(lambda t: t.name == "json_spec_get_value", libertai_tools)
    assert list_keys_tool is not None
    assert get_value_tool is not None


def test_langchain_requests_tools():
    # https://python.langchain.com/docs/integrations/tools/requests/
    toolkit = RequestsToolkit(
        requests_wrapper=TextRequestsWrapper(headers={}),
        allow_dangerous_requests=True,
    )
    tools = toolkit.get_tools()

    libertai_tools = [Tool.from_langchain(t) for t in tools]
    get_tool = find(lambda t: t.name == "requests_get", libertai_tools)
    assert get_tool is not None


# TODO: add tests for the following tools:
# https://python.langchain.com/docs/integrations/tools/nasa/
# https://python.langchain.com/docs/integrations/tools/openweathermap/
