import os

from dotenv import load_dotenv


class _Config:
    ALEPH_API_URL: str | None

    ALEPH_SENDER: str
    ALEPH_OWNER: str
    ALEPH_SENDER_SK: bytes
    ALEPH_SENDER_PK: bytes
    ALEPH_CHANNEL: str
    ALEPH_AGENT_POST_TYPE: str

    SUBSCRIPTION_BACKEND_URL: str
    SUBSCRIPTION_BACKEND_PASSWORD: str

    def __init__(self):
        load_dotenv()

        self.ALEPH_API_URL = os.getenv("ALEPH_API_URL")
        self.ALEPH_SENDER = os.getenv("ALEPH_SENDER")
        self.ALEPH_OWNER = os.getenv("ALEPH_OWNER")
        self.ALEPH_SENDER_SK = os.getenv("ALEPH_SENDER_SK")  # type: ignore
        self.ALEPH_SENDER_PK = os.getenv("ALEPH_SENDER_PK")  # type: ignore
        self.ALEPH_CHANNEL = os.getenv("ALEPH_CHANNEL", "libertai")
        self.ALEPH_AGENT_POST_TYPE = os.getenv(
            "ALEPH_AGENT_POST_TYPE", "libertai-agent"
        )

        self.SUBSCRIPTION_BACKEND_URL = os.getenv("SUBSCRIPTION_BACKEND_URL")
        self.SUBSCRIPTION_BACKEND_PASSWORD = os.getenv("SUBSCRIPTION_BACKEND_PASSWORD")


config = _Config()
