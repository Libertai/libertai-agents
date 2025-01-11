import io
import time
from http import HTTPStatus
from uuid import uuid4

import aiohttp
import paramiko
from aleph.sdk import AuthenticatedAlephHttpClient
from aleph.sdk.chains.ethereum import ETHAccount
from aleph.sdk.conf import settings
from aleph_message.models import Chain, Payment, PaymentType, StoreMessage
from aleph_message.models.execution.environment import HypervisorType
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from libertai_utils.chains.index import is_signature_valid
from libertai_utils.interfaces.agent import UpdateAgentResponse
from libertai_utils.interfaces.subscription import Subscription
from libertai_utils.utils.crypto import decrypt, encrypt
from starlette.middleware.cors import CORSMiddleware

from src.config import config
from src.interfaces.agent import (
    Agent,
    AgentPythonPackageManager,
    AgentUsageType,
    DeleteAgentBody,
    GetAgentResponse,
    GetAgentSecretMessage,
    GetAgentSecretResponse,
    SetupAgentBody,
)
from src.utils.agent import fetch_agents
from src.utils.aleph import fetch_instance_ip
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
    encrypted_private_key = encrypt(private_key, config.ALEPH_SENDER_PK)

    rootfs = settings.UBUNTU_22_QEMU_ROOTFS_ID

    aleph_account = ETHAccount(config.ALEPH_SENDER_SK)
    async with AuthenticatedAlephHttpClient(
        account=aleph_account, api_server=config.ALEPH_API_URL
    ) as client:
        rootfs_message: StoreMessage = await client.get_message(
            item_hash=rootfs, message_type=StoreMessage
        )
        rootfs_size = (
            rootfs_message.content.size
            if rootfs_message.content.size is not None
            else settings.DEFAULT_ROOTFS_SIZE
        )

        instance_message, _status = await client.create_instance(
            rootfs=rootfs,
            rootfs_size=rootfs_size,
            hypervisor=HypervisorType.qemu,
            payment=Payment(chain=Chain.ETH, type=PaymentType.hold, receiver=None),
            channel=config.ALEPH_CHANNEL,
            address=config.ALEPH_OWNER,
            ssh_keys=[public_key],
            metadata={"name": agent_id},
            vcpus=settings.DEFAULT_VM_VCPUS,
            memory=settings.DEFAULT_INSTANCE_MEMORY,
            sync=True,
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

    try:
        ip_address = await fetch_instance_ip(agent.instance_hash)
    except ValueError:
        ip_address = None

    return GetAgentResponse(
        id=agent.id,
        instance_hash=agent.instance_hash,
        instance_ip=ip_address,
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
    deploy_script_url: str = Form(
        default="https://raw.githubusercontent.com/Libertai/libertai-agents/refs/heads/reza/instances/deployment/deploy.sh"
    ),
    python_version: str = Form(),
    usage_type: AgentUsageType = Form(),
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

    try:
        hostname = await fetch_instance_ip(agent.instance_hash)
    except ValueError:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Instance IPv6 address not found, it probably isn't allocated yet. Please try again in a few minutes.",
        )

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

    # Execute the command
    ssh_client.exec_command(
        f"wget {deploy_script_url} -O /tmp/deploy-agent.sh -q --no-cache && chmod +x /tmp/deploy-agent.sh && /tmp/deploy-agent.sh {python_version} {package_manager.value} {usage_type.value}"
    )

    # Close the connection
    ssh_client.close()

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

    return UpdateAgentResponse(instance_ip=hostname)


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
