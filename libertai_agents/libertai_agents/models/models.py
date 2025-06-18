import typing

from huggingface_hub import login
from pydantic import BaseModel

from libertai_agents.models.base import Model, ModelId
from libertai_agents.models.hermes import HermesModel


class ModelConfiguration(BaseModel):
    context_length: int
    ltai_id: str


class FullModelConfiguration(ModelConfiguration):
    constructor: typing.Type[Model]


MODEL_IDS: list[ModelId] = list(typing.get_args(ModelId))

MODELS_CONFIG: dict[ModelId, FullModelConfiguration] = {
    "NousResearch/Hermes-3-Llama-3.1-8B": FullModelConfiguration(
        context_length=16384,
        constructor=HermesModel,
        ltai_id="hermes-3-8b-tee",
    ),
    "unsloth/gemma-3-27b-it": FullModelConfiguration(
        context_length=32768,
        constructor=HermesModel,
        ltai_id="gemma-3-27b",
    ),
}


def get_model(
    model_id: ModelId,
    hf_token: str | None = None,
    custom_configuration: ModelConfiguration | None = None,
) -> Model:
    """
    Get one of the available models

    :param model_id: HuggingFace ID of the model, must be one of the supported models
    :param hf_token: Optional access token, required to use gated models
    :param custom_configuration: Optional model configuration (useful to use a local model)
    :return: An instance of the model
    """

    # Fetching our full configuration with the model constructor
    full_config = MODELS_CONFIG.get(model_id)

    if full_config is None:
        raise ValueError(f"model_id must be one of {MODEL_IDS}")

    if hf_token is not None:
        login(hf_token)

    # Using our configuration if the user didn't pass a custom model config
    configuration = (
        custom_configuration if custom_configuration is not None else full_config
    )

    return full_config.constructor(
        model_id=model_id, **configuration.model_dump(exclude={"constructor"})
    )
