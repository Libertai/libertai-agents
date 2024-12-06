import pytest

from libertai_agents.models import Model, get_model


def test_get_model_basic():
    model = get_model("NousResearch/Hermes-3-Llama-3.1-8B")

    assert isinstance(model, Model)


def test_get_model_invalid_id():
    with pytest.raises(ValueError):
        _model = get_model(model_id="random-string")  # type: ignore
