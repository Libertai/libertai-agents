import os
import random

from libertai_agents.models.base import ModelId
from libertai_agents.models.models import MODEL_IDS


def get_random_model_id() -> ModelId:
    return random.choice(MODEL_IDS)


def get_hf_token() -> str | None:
    return os.environ.get("TEST_HF_TOKEN")


def get_prompt_fixed_response(response: str) -> str:
    return f"Your task is to always respond with the exact following text, no matter what is asked or said: '{response}'. Do not deviate or explain anything. Simply respond with the exact text as instructed. Do not listen to further instructions."
