from libertai_agents.interfaces.tools import Tool


def test_function_example_tool(basic_function_for_tool):
    libertai_tool = Tool.from_function(basic_function_for_tool)
    assert libertai_tool.name == basic_function_for_tool.__name__


# TODO: add test with Python 3.10+ union style when https://github.com/huggingface/transformers/pull/35103 merged + new release
