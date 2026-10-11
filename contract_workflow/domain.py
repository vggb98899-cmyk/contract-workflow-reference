from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from typing import Any


@dataclass(frozen=True)
class Target:
    supplier_key: str
    period: str


@dataclass(frozen=True)
class ContractLine:
    external_id: str
    item_name: str
    quantity: int
    amount: Decimal


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str
    target: Target
    captured_at: datetime
    schema_version: int
    lines: tuple[ContractLine, ...]


@dataclass(frozen=True)
class Plan:
    plan_id: str
    target: Target
    snapshot_id: str
    created_at: datetime
    lines: tuple[ContractLine, ...]
    digest: str


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


def build_plan(target: Target, snapshot: Snapshot) -> Plan:
    payload = {
        "target": asdict(target),
        "snapshot_id": snapshot.snapshot_id,
        "lines": [asdict(line) for line in snapshot.lines],
    }
    digest = canonical_digest(payload)
    return Plan(
        plan_id=f"plan-{digest[:16]}",
        target=target,
        snapshot_id=snapshot.snapshot_id,
        created_at=datetime.now(timezone.utc),
        lines=snapshot.lines,
        digest=digest,
    )
