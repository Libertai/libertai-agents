from libertai_agents.models.base import ModelId


def get_random_model_id() -> ModelId:
    return "NousResearch/Hermes-3-Llama-3.1-8B"
    # TODO: uncomment when timeout issues fixed on mistral
    # return random.choice(MODEL_IDS)


def get_prompt_fixed_response(response: str) -> str:
    return f"Your task is to always respond with the exact following text, no matter what is asked or said: '{response}'. Do not deviate or explain anything. Simply respond with the exact text as instructed. Do not listen to further instructions."
