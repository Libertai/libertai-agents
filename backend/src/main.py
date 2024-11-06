import time
from http import HTTPStatus
from uuid import uuid4

import aiohttp
from aleph.sdk import AuthenticatedAlephHttpClient
from aleph.sdk.chains.ethereum import ETHAccount
from aleph_message.models.execution import Encoding
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from libertai_utils.chains.index import is_signature_valid
from libertai_utils.interfaces.subscription import Subscription
from libertai_utils.utils.crypto import decrypt, encrypt
from starlette.middleware.cors import CORSMiddleware

from src.config import config
from src.interfaces.agent import (
    Agent,
    SetupAgentBody,
    DeleteAgentBody,
    UpdateAgentResponse,
    GetAgentResponse,
    GetAgentSecretResponse,
    GetAgentSecretMessage,
)
from src.interfaces.aleph import AlephVolume
from src.utils.agent import fetch_agents, fetch_agent_program_message
from src.utils.message import get_view_agent_secret_message
from src.utils.storage import upload_file

app = FastAPI(title="LibertAI agents")

origins = [
    "https://chat.libertai.io",
    "http://localhost:9000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/agent", description="Setup a new agent on subscription")
async def setup(body: SetupAgentBody) -> None:
    agent_id = str(uuid4())

    secret = str(uuid4())
    encrypted_secret = encrypt(secret, config.ALEPH_SENDER_PK)

    agent = Agent(
        id=agent_id,
        subscription_id=body.subscription_id,
        vm_hash=None,
        encrypted_secret=encrypted_secret,
        last_update=int(time.time()),
        tags=[agent_id, body.subscription_id, body.account.address],
    )

    aleph_account = ETHAccount(config.ALEPH_SENDER_SK)
    async with AuthenticatedAlephHttpClient(
        account=aleph_account, api_server=config.ALEPH_API_URL
    ) as client:
        post_message, _ = await client.create_post(
            address=config.ALEPH_OWNER,
            post_content=agent.dict(),
            post_type=config.ALEPH_AGENT_POST_TYPE,
            channel=config.ALEPH_CHANNEL,
        )


@app.get("/agent/{agent_id}", description="Get an agent public information")
async def get_agent_public_info(agent_id: str) -> GetAgentResponse:
    """Get an agent by an ID (either agent ID or subscription ID)"""
    agents = await fetch_agents([agent_id])

    if len(agents) != 1:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Agent with ID {agent_id} not found.",
        )
    agent = agents[0]

    return GetAgentResponse(
        id=agent.id, vm_hash=agent.vm_hash, last_update=agent.last_update
    )


@app.get("/agent/{agent_id}/secret", description="Get an agent secret")
async def get_agent_secret(agent_id: str, signature: str) -> GetAgentSecretResponse:
    agents = await fetch_agents([agent_id])

    if len(agents) != 1:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Agent with ID {agent_id} not found.",
        )
    agent = agents[0]

    async with aiohttp.ClientSession() as session:
        async with session.get(
            url=f"{config.SUBSCRIPTION_BACKEND_URL}/subscriptions/{agent.subscription_id}"
        ) as response:
            data = await response.json()
            if response.status != HTTPStatus.OK:
                raise HTTPException(
                    status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                    detail=f"Subscriptions API returned a non-200 code: {data}",
                )
            subscription = Subscription(**data)

    valid_signature = is_signature_valid(
        subscription.account.chain,
        get_view_agent_secret_message(agent_id),
        signature,
        subscription.account.address,
    )

    if not valid_signature:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="The signature doesn't match the owner of this agent subscription",
        )

    decrypted_secret = decrypt(agent.encrypted_secret, config.ALEPH_SENDER_SK)

    return GetAgentSecretResponse(secret=decrypted_secret)


@app.get(
    "/agent/{agent_id}/secret-message",
    description="Get the message to fetch an agent secret",
)
def get_agent_secret_message(agent_id: str) -> GetAgentSecretMessage:
    return GetAgentSecretMessage(message=get_view_agent_secret_message(agent_id))


@app.put("/agent/{agent_id}", description="Deploy an agent or update it")
async def update(
    agent_id: str,
    secret: str = Form(),
    code: UploadFile = File(...),
    packages: UploadFile = File(...),
) -> UpdateAgentResponse:
    agents = await fetch_agents([agent_id])

    if len(agents) != 1:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Agent with ID {agent_id} not found.",
        )
    agent = agents[0]
    agent_program = (
        await fetch_agent_program_message(agent.vm_hash)
        if agent.vm_hash is not None
        else None
    )

    decrypted_secret = decrypt(agent.encrypted_secret, config.ALEPH_SENDER_SK)

    if secret != decrypted_secret:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="The secret provided doesn't match the one of this agent.",
        )

    previous_code_ref = (
        agent_program.content.code.ref if agent_program is not None else None
    )
    # TODO: additional checks on the type of volume, find the right one based on mount etc
    previous_packages_ref = (
        agent_program.content.volumes[0].ref if agent_program is not None else None  # type: ignore
    )

    code_ref = await upload_file(code, previous_code_ref)
    packages_ref = await upload_file(packages, previous_packages_ref)

    # Register the program
    aleph_account = ETHAccount(config.ALEPH_SENDER_SK)
    async with AuthenticatedAlephHttpClient(
        account=aleph_account, api_server=config.ALEPH_API_URL
    ) as client:
        vm_hash = agent.vm_hash

        if vm_hash is None:
            message, _ = await client.create_program(
                address=config.ALEPH_OWNER,
                program_ref=code_ref,
                entrypoint="run",
                runtime="63f07193e6ee9d207b7d1fcf8286f9aee34e6f12f101d2ec77c1229f92964696",
                channel=config.ALEPH_CHANNEL,
                encoding=Encoding.squashfs,
                persistent=False,
                volumes=[
                    AlephVolume(
                        comment="Python packages",
                        mount="/opt/packages",
                        ref=packages_ref,
                        use_latest=True,
                    ).dict()
                ],
            )
            vm_hash = message.item_hash

        # Updating the related POST message
        await client.create_post(
            address=config.ALEPH_OWNER,
            post_content=Agent(
                **agent.dict(exclude={"vm_hash", "last_update"}),
                vm_hash=vm_hash,
                last_update=int(time.time()),
            ),
            post_type="amend",
            ref=agent.post_hash,
            channel=config.ALEPH_CHANNEL,
        )
    return UpdateAgentResponse(vm_hash=vm_hash)


@app.delete("/agent", description="Remove an agent on subscription end")
async def delete(body: DeleteAgentBody):
    # TODO
    pass
