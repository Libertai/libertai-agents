from __future__ import annotations

from dataclasses import MISSING, dataclass, field, fields
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
        all_fields = list(fields(cls))
        known = {f.name for f in all_fields}
        required = {
            f.name
            for f in all_fields
            if f.default is MISSING and f.default_factory is MISSING
        }
        missing = required - data.keys()
        if missing:
            raise ValueError(
                f"Missing required PaymentRequirements field(s): {', '.join(sorted(missing))}"
            )
        values = {k: v for k, v in data.items() if k in known}
        extra = values.get("extra")
        if extra is None:
            values["extra"] = {}
        elif not isinstance(extra, dict):
            raise ValueError("PaymentRequirements 'extra' must be an object")
        return cls(**values)

    @property
    def primary_type(self) -> str:
        return self.extra.get("primaryType", "TransferWithAuthorization")
