from pydantic.main import BaseModel


class AlephVolume(BaseModel):
    comment: str
    mount: str
    ref: str
    use_latest: bool
