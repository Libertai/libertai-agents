import pytest

from libertai_agents.models import Model, get_model
from tests.utils.models import get_random_model_id


def test_get_model_basic():
    model = get_model(get_random_model_id())

    assert isinstance(model, Model)


def test_get_model_invalid_id():
    with pytest.raises(ValueError):
        _model = get_model(model_id="random-string")  # type: ignore
