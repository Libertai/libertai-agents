import aiohttp


async def fetch_instance_ip(item_hash: str) -> str:
    """
    Fetches IPv6 of an allocated instance given a message hash.

    Args:
        item_hash: Instance message hash.
    Returns:
        IPv6 address
    """

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"https://scheduler.api.aleph.cloud/api/v0/allocation/{item_hash}"
            ) as resp:
                resp.raise_for_status()
                allocation = await resp.json()
                return allocation["vm_ipv6"]
        except (
            aiohttp.ClientResponseError,
            aiohttp.ClientConnectorError,
            aiohttp.ConnectionTimeoutError,
        ):
            raise ValueError()
