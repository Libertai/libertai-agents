import aiohttp
from aleph.sdk import AlephHttpClient
from aleph_message.models import InstanceMessage

from src.config import config


async def fetch_instance_ip(item_hash) -> str:
    """
    Fetches IPv6 of an allocated instance given a message hash.

    Args:
        item_hash: Instance message hash.
    Returns:
        IPv6 address
    """
    async with AlephHttpClient(api_server=config.ALEPH_API_URL) as client:
        message = await client.get_message(item_hash, InstanceMessage)

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"https://scheduler.api.aleph.cloud/api/v0/allocation/{message.item_hash}"
            ) as resp:
                resp.raise_for_status()
                allocation = await resp.json()
                return allocation["vm_ipv6"]
        except (aiohttp.ClientResponseError, aiohttp.ClientConnectorError):
            raise ValueError()
