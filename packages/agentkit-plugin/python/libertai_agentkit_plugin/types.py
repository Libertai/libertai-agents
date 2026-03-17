from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class ToolExecution(BaseModel):
    name: str
    args: Optional[dict[str, str]] = None
    result: Optional[str] = None
    tx_hash: Optional[str] = None
    meta: Optional[dict[str, str]] = None


class ActivityType(str, Enum):
    inventory = "inventory"
    survival = "survival"
    strategy = "strategy"
    error = "error"


class AgentActivity(BaseModel):
    summary: str
    model: str
    cycle_id: str
    tools: Optional[list[ToolExecution]] = None
    tx_hashes: Optional[list[str]] = None
