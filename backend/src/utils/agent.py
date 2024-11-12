from aleph.sdk import AlephHttpClient
from aleph.sdk.query.filters import PostFilter
from aleph_message.models import ProgramMessage

from src.config import config
from src.interfaces.agent import FetchedAgent


async def fetch_agents(ids: list[str] | None = None) -> list[FetchedAgent]:
    async with AlephHttpClient(api_server=config.ALEPH_API_URL) as client:
        result = await client.get_posts(
            post_filter=PostFilter(
                types=[config.ALEPH_AGENT_POST_TYPE],
                addresses=[config.ALEPH_OWNER],
                tags=ids,
                channels=[config.ALEPH_CHANNEL],
            )
        )
    return [
        FetchedAgent(**post.content, post_hash=post.original_item_hash)
        for post in result.posts
    ]


async def fetch_agent_program_message(item_hash: str) -> ProgramMessage:
    async with AlephHttpClient(api_server=config.ALEPH_API_URL) as client:
        result = await client.get_message(item_hash, ProgramMessage)
        return result
