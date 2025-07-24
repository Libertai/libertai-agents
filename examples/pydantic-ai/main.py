import os
import random

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

load_dotenv()

app = FastAPI(
    title="LibertAI x Pydantic AI Example",
)

# Custom provider to use LibertAI
model = OpenAIModel(
    "hermes-3-8b-tee",
    provider=OpenAIProvider(
        base_url="https://api.libertai.io/v1", api_key=os.getenv("LIBERTAI_API_KEY")
    ),
)


agent = Agent(
    model=model,
    deps_type=str,
    system_prompt=(
        "You're a dice game, you should roll the die and see if the number "
        "you get back matches the user's guess. If so, tell them they're a winner. "
        "Use the player's name in the response."
    ),
)


@agent.tool_plain
def roll_dice() -> str:
    """Roll a six-sided die and return the result."""
    return str(random.randint(1, 6))


@agent.tool
def get_player_name(ctx: RunContext[str]) -> str:
    """Get the player's name."""
    return ctx.deps


class PromptRequest(BaseModel):
    prompt: str
    player_name: str


class PromptResponse(BaseModel):
    response: str


@app.post("/chat")
async def chat(request: PromptRequest) -> PromptResponse:
    result = await agent.run(request.prompt, deps=request.player_name)
    return PromptResponse(response=result.output)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
