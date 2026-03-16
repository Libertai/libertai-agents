from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any


@dataclass
class PaymentRequirements:
    scheme: str
    network: str
    maxAmountRequired: str
    resource: str
    payTo: str
    maxTimeoutSeconds: int
    asset: str
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PaymentRequirements:
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    @property
    def name(self) -> str:
        return self.extra.get("name", "")

    @property
    def version(self) -> str:
        return self.extra.get("version", "")

    @property
    def primary_type(self) -> str:
        return self.extra.get("primaryType", "TransferWithAuthorization")
