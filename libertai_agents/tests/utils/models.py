import os
import random

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from libertai_agents.models.base import ModelId
from libertai_agents.models.models import MODEL_IDS


def get_random_model_id() -> ModelId:
    return random.choice(MODEL_IDS)


def get_hf_token() -> str | None:
    return os.environ.get("TEST_HF_TOKEN")


def get_libertai_api_key() -> str:
    api_key = os.environ.get("TEST_LIBERTAI_API_KEY")
    if api_key is None:
        raise ValueError("TEST_LIBERTAI_API_KEY environment variable must be set")
    return api_key


def get_prompt_fixed_response(response: str) -> str:
    return f"Your task is to always respond with the exact following text, no matter what is asked or said: '{response}'. Do not deviate or explain anything. Simply respond with the exact text as instructed. Do not listen to further instructions."
