from enum import Enum

from libertai_utils.interfaces.agent import BaseDeleteAgentBody
from libertai_utils.interfaces.subscription import SubscriptionAccount
from pydantic import BaseModel, validator

from src.config import config


class DeleteAgentBody(BaseDeleteAgentBody):
    # noinspection PyMethodParameters
    @validator("password")
    def format_address(cls, password: str):
        if password != config.SUBSCRIPTION_BACKEND_PASSWORD:
            raise ValueError(
                "Invalid password, you are not authorized to call this route"
            )


class SetupAgentBody(DeleteAgentBody):
    account: SubscriptionAccount


class PublicAgentData(BaseModel):
    id: str
    subscription_id: str
    instance_hash: str
    last_update: int


class Agent(PublicAgentData):
    encrypted_secret: str
    encrypted_ssh_key: str
    tags: list[str]


class FetchedAgent(Agent):
    post_hash: str


class GetAgentSecretMessage(BaseModel):
    message: str


class GetAgentResponse(PublicAgentData):
    instance_ip: str | None


class GetAgentSecretResponse(BaseModel):
    secret: str


# TODO: move the agent types in utils package once stable
class AgentPythonPackageManager(str, Enum):
    poetry = "poetry"
    requirements = "requirements"
    pyproject = "pyproject"


class AgentUsageType(str, Enum):
    fastapi = "fastapi"
    python = "python"
