from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable

from .domain import ContractLine, Snapshot, Target


class TransientReadError(RuntimeError):
    pass


class NonRetryableReadError(RuntimeError):
    pass


class UnknownWriteResult(RuntimeError):
    pass


class MockProcurementGateway:
    """Offline external-system stand-in. It never contacts an ERP or browser."""

    expected_schema = {"external_id", "item_name", "quantity", "amount"}

    def __init__(self, records: Iterable[dict[str, object]], failures: Iterable[str] = ()) -> None:
        self.records = list(records)
        self.failures = Counter(failures)
        self.writes: dict[str, dict[str, object]] = {}

    def fetch(self, target: Target) -> Snapshot:
        if self.failures["transient_read"]:
            self.failures["transient_read"] -= 1
            raise TransientReadError("mock transient read failure")
        if self.failures["nonretryable_read"]:
            self.failures["nonretryable_read"] -= 1
            raise NonRetryableReadError("mock non-retryable read failure")
        selected = [item for item in self.records if item.get("supplier_key") == target.supplier_key and item.get("period") == target.period]
        lines = tuple(
            ContractLine(str(item["external_id"]), str(item["item_name"]), int(item["quantity"]), Decimal(str(item["amount"])))
            for item in selected
        )
        return Snapshot(f"snapshot-{target.supplier_key}-{target.period}", target, datetime.now(timezone.utc), 1, lines)

    def write_contract(self, plan_key: str, rendered: str) -> str:
        if self.failures["unknown_write"]:
            self.failures["unknown_write"] -= 1
            self.writes[plan_key] = {"rendered": rendered, "readback": rendered}
            raise UnknownWriteResult("write outcome is intentionally unknown")
        if self.failures["readback_mismatch"]:
            self.failures["readback_mismatch"] -= 1
            self.writes[plan_key] = {"rendered": rendered, "readback": "tampered"}
        else:
            self.writes[plan_key] = {"rendered": rendered, "readback": rendered}
        return f"mock://contracts/{plan_key}"

    def reconcile_write(self, plan_key: str) -> bool:
        return plan_key in self.writes

    def read_back(self, plan_key: str) -> str:
        return str(self.writes[plan_key]["readback"])

    @classmethod
    def example_records(cls) -> list[dict[str, object]]:
        return [
            {"supplier_key": "supplier-alpha", "period": "2026-06", "external_id": "PO-DEMO-001", "item_name": "Sample textile A", "quantity": 12, "amount": "180.00"},
            {"supplier_key": "supplier-alpha", "period": "2026-06", "external_id": "PO-DEMO-002", "item_name": "Sample textile B", "quantity": 8, "amount": "160.00"},
        ]
