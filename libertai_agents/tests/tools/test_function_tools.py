from libertai_agents.interfaces.tools import Tool


def test_function_example_tool(fake_get_temperature_tool):
    libertai_tool = Tool.from_function(fake_get_temperature_tool)
    assert libertai_tool.name == fake_get_temperature_tool.__name__


def test_function_new_union_style_param_tool(
    fake_get_temperature_with_new_union_style_param_tool,
):
    libertai_tool = Tool.from_function(
        fake_get_temperature_with_new_union_style_param_tool
    )
    print(libertai_tool.args_schema)
    assert (
        libertai_tool.name
        == fake_get_temperature_with_new_union_style_param_tool.__name__
    )
    assert libertai_tool.args_schema


# TODO: add test with Python 3.10+ union style when https://github.com/huggingface/transformers/pull/35103 merged + new release
