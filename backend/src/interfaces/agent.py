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


class UpdateAgentResponse(BaseModel):
    vm_hash: str


class PublicAgentData(BaseModel):
    id: str
    vm_hash: str | None
    last_update: int


class Agent(PublicAgentData):
    subscription_id: str
    encrypted_secret: str
    tags: list[str]


class FetchedAgent(Agent):
    post_hash: str


class GetAgentSecretMessage(BaseModel):
    message: str


class GetAgentResponse(PublicAgentData):
    pass


class GetAgentSecretResponse(BaseModel):
    secret: str
