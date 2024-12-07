import io
import time
from http import HTTPStatus
from uuid import uuid4

import aiohttp
import paramiko
from aleph.sdk import AuthenticatedAlephHttpClient
from aleph.sdk.chains.ethereum import ETHAccount
from aleph_message.models import Payment, Chain, PaymentType
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
    AgentPythonPackageManager,
)
from src.utils.agent import fetch_agents
from src.utils.message import get_view_agent_secret_message
from src.utils.ssh import generate_ssh_key_pair

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

    private_key, public_key = generate_ssh_key_pair()
    encrypted_private_key = encrypt(private_key, config.ALEPH_SENDER_SK)

    aleph_account = ETHAccount(config.ALEPH_SENDER_SK)
    async with AuthenticatedAlephHttpClient(
        account=aleph_account, api_server=config.ALEPH_API_URL
    ) as client:
        instance_message, _status = await client.create_instance(
            rootfs="TODO",
            rootfs_size=0,
            payment=Payment(chain=Chain.ETH, type=PaymentType.hold, receiver=None),
            channel=config.ALEPH_CHANNEL,
            address=config.ALEPH_OWNER,
            ssh_keys=[public_key],
        )

        agent = Agent(
            id=agent_id,
            subscription_id=body.subscription_id,
            instance_hash=instance_message.item_hash,
            encrypted_secret=encrypted_secret,
            encrypted_ssh_key=encrypted_private_key,
            last_update=int(time.time()),
            tags=[agent_id, body.subscription_id, body.account.address],
        )

        await client.create_post(
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
        id=agent.id,
        instance_hash=agent.instance_hash,
        last_update=agent.last_update,
        subscription_id=agent.subscription_id,
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
    python_version: str = Form(),
    package_manager: AgentPythonPackageManager = Form(),
    code: UploadFile = File(...),
) -> UpdateAgentResponse:
    agents = await fetch_agents([agent_id])

    if len(agents) != 1:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Agent with ID {agent_id} not found.",
        )
    agent = agents[0]

    # Validating the secret
    decrypted_secret = decrypt(agent.encrypted_secret, config.ALEPH_SENDER_SK)
    if secret != decrypted_secret:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="The secret provided doesn't match the one of this agent.",
        )

    ssh_private_key = decrypt(agent.encrypted_ssh_key, config.ALEPH_SENDER_SK)

    # TODO: get hostname using instance_hash
    hostname = "2a01:240:ad00:2100:3:89cf:401:4871"

    # TODO: store link elsewhere, use main version and take as optional parameter in route
    SCRIPT_URL = "https://raw.githubusercontent.com/Libertai/libertai-agents/refs/heads/reza/deployment-instances/deployment/deploy.sh"

    # Create a Paramiko SSH client
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Load private key from string
    rsa_key = paramiko.RSAKey(file_obj=io.StringIO(ssh_private_key))

    # Read the file content into memory
    content = await code.read()

    # Connect to the server
    ssh_client.connect(hostname=hostname, username="root", pkey=rsa_key)

    # Send the zip with the code
    sftp = ssh_client.open_sftp()
    remote_path = "/tmp/libertai-agent.zip"
    sftp.putfo(io.BytesIO(content), remote_path)
    sftp.close()

    # Execute a command
    _stdin, stdout, stderr = ssh_client.exec_command(
        f"wget {SCRIPT_URL} -O /tmp/deploy-agent.sh -q --no-cached && chmod +x /tmp/deploy-agent.sh && /tmp/deploy-agent.sh {python_version} {package_manager.value}"
    )

    output = stdout.read().decode("utf-8")
    error = stderr.read().decode("utf-8")
    # Close the connection
    ssh_client.close()

    print("Command Output:")
    print(output)

    if error:
        print("Command Error:")
        print(error)

    # Register the program
    aleph_account = ETHAccount(config.ALEPH_SENDER_SK)
    async with AuthenticatedAlephHttpClient(
        account=aleph_account, api_server=config.ALEPH_API_URL
    ) as client:
        # Updating the related POST message
        await client.create_post(
            address=config.ALEPH_OWNER,
            post_content=Agent(
                **agent.dict(exclude={"last_update"}),
                last_update=int(time.time()),
            ),
            post_type="amend",
            ref=agent.post_hash,
            channel=config.ALEPH_CHANNEL,
        )

    return UpdateAgentResponse(instance_hash="TODO")


@app.delete("/agent", description="Remove an agent on subscription end")
async def delete(body: DeleteAgentBody):
    agents = await fetch_agents([body.subscription_id])

    if len(agents) != 1:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Agent for subscription ID {body.subscription_id} not found.",
        )
    agent = agents[0]

    aleph_account = ETHAccount(config.ALEPH_SENDER_SK)
    async with AuthenticatedAlephHttpClient(
        account=aleph_account, api_server=config.ALEPH_API_URL
    ) as client:
        await client.forget(
            address=config.ALEPH_OWNER,
            hashes=[agent.instance_hash],
            channel=config.ALEPH_CHANNEL,
            reason="LibertAI Agent subscription ended",
        )
