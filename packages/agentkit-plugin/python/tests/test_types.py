from libertai_agentkit_plugin.types import ActivityType, AgentActivity, ToolExecution


def test_tool_execution_minimal():
    te = ToolExecution(name="echo")
    assert te.name == "echo"
    assert te.args is None
    assert te.result is None


def test_tool_execution_full():
    te = ToolExecution(name="buy", args={"amount": "10"}, result="ok", tx_hash="0xabc")
    assert te.args == {"amount": "10"}
    assert te.tx_hash == "0xabc"


def test_activity_type_values():
    assert "inventory" in ActivityType.__members__
    assert "error" in ActivityType.__members__


def test_agent_activity():
    act = AgentActivity(summary="cycle 1", model="qwen", cycle_id="c1")
    assert act.tools is None
    assert act.tx_hashes is None
