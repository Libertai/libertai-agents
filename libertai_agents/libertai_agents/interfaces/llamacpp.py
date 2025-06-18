from pydantic import BaseModel


class CustomizableLlamaCppParams(BaseModel):
    stream: bool = False


class LlamaCppParams(CustomizableLlamaCppParams):
    prompt: str
    model: str
