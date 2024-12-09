from pydantic.main import BaseModel


class AlephVolume(BaseModel):
    comment: str
    mount: str
    ref: str
    use_latest: bool


class AlephNodeInfo:
    def __init__(self, **kwargs):
        self.data = kwargs.get("data", {})
        self.nodes = self.data.get("corechannel", {}).get("resource_nodes", [])
        self.nodes.sort(key=lambda x: x.get("score", 0), reverse=True)
        self.core_node = self.data.get("corechannel", {}).get("nodes", [])
        self.core_node.sort(key=lambda x: x.get("score", 0), reverse=True)
