from typing import Any

import aiohttp
from aleph.sdk import AuthenticatedAlephHttpClient
from aleph.sdk.chains.ethereum import ETHAccount
from aleph.sdk.types import StorageEnum
from aleph_message.models import ItemHash
from starlette.datastructures import UploadFile

from src.config import config

MAX_DIRECT_STORE_SIZE = 50 * 1024 * 1024  # 50MB


async def __upload_on_ipfs(file_content: Any, filename: str | None = None) -> str:
    """Upload a file on the IPFS gateway of Aleph and return the CID"""
    async with aiohttp.ClientSession() as session:
        form_data = aiohttp.FormData()
        form_data.add_field("file", file_content, filename=filename)
        response = await session.post(
            url="https://ipfs.aleph.cloud/api/v0/add", data=form_data
        )
        ipfs_data = await response.json()
        return ipfs_data["Hash"]


async def upload_file(file: UploadFile, previous_ref: ItemHash | None = None) -> str:
    """Upload a file on Aleph, using an IPFS gateway if needed, and returns the STORE message ref"""

    file_content = await file.read()
    file_size = len(file_content)
    storage_engine = (
        StorageEnum.ipfs if file_size > 4 * 1024 * 1024 else StorageEnum.storage
    )

    aleph_account = ETHAccount(config.ALEPH_SENDER_SK)
    async with AuthenticatedAlephHttpClient(
        account=aleph_account, api_server=config.ALEPH_API_URL
    ) as client:
        if file_size > MAX_DIRECT_STORE_SIZE:
            ipfs_hash = await __upload_on_ipfs(file_content, file.filename)
            store_message, _ = await client.create_store(
                address=config.ALEPH_OWNER,
                ref=previous_ref,
                file_hash=ipfs_hash,
                storage_engine=storage_engine,
                channel=config.ALEPH_CHANNEL,
                guess_mime_type=True,
            )
        else:
            store_message, _ = await client.create_store(
                address=config.ALEPH_OWNER,
                ref=previous_ref,
                file_content=file_content,
                storage_engine=storage_engine,
                channel=config.ALEPH_CHANNEL,
                guess_mime_type=True,
            )
        return store_message.item_hash
