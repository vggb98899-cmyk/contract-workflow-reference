from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from time import sleep
from typing import Callable

from .domain import Plan, Snapshot, Target, build_plan
from .mock_gateway import NonRetryableReadError, TransientReadError, UnknownWriteResult
from .store import JsonStore


class WorkflowError(RuntimeError):
    pass


class ContractWorkflow:
    """Fail-closed preview → immutable plan → idempotent write reference workflow."""

    def __init__(self, gateway: object, store: JsonStore, now: Callable[[], datetime] | None = None) -> None:
        self.gateway, self.store, self.now = gateway, store, now or (lambda: datetime.now(timezone.utc))

    def preview(self, target: Target, max_lines: int = 100, snapshot_ttl_seconds: int = 300) -> Plan:
        snapshot = self._fetch_with_retry(target)
        self._validate_snapshot(target, snapshot, max_lines, snapshot_ttl_seconds)
        plan = build_plan(target, snapshot)
        state = self.store.read()
        state.setdefault("plans", {})[plan.plan_id] = self._serialise_plan(plan)
        self.store.write(state)
        return plan

    def execute(self, plan_id: str, expected_target: Target) -> dict[str, str]:
        state = self.store.read()
        record = state.get("plans", {}).get(plan_id)
        if not record:
            raise WorkflowError("unknown plan")
        target = Target(**record["target"])
        if target != expected_target:
            raise WorkflowError("target mismatch")
        if record.get("status") == "SUCCESS":
            return {"status": "IDEMPOTENT_SUCCESS", "reference": record["reference"]}
        if record.get("status") == "UNKNOWN":
            raise WorkflowError("unknown prior write: reconcile before retry")
        rendered = self._render(record)
        record["status"] = "PREPARED"
        self.store.write(state)
        try:
            reference = self.gateway.write_contract(plan_id, rendered)
        except UnknownWriteResult:
            record["status"] = "UNKNOWN"
            self.store.write(state)
            raise WorkflowError("unknown write: duplicate retry blocked") from None
        if self.gateway.read_back(plan_id) != rendered:
            record["status"] = "READBACK_FAILED"
            self.store.write(state)
            raise WorkflowError("read-back mismatch")
        record.update({"status": "SUCCESS", "reference": reference})
        self.store.write(state)
        return {"status": "SUCCESS", "reference": reference}

    def recover(self, plan_id: str) -> dict[str, str]:
        state = self.store.read()
        record = state.get("plans", {}).get(plan_id)
        if not record or record.get("status") not in {"PREPARED", "UNKNOWN"}:
            raise WorkflowError("no recoverable plan")
        if not self.gateway.reconcile_write(plan_id):
            record["status"] = "REQUIRES_MANUAL_REVIEW"
            self.store.write(state)
            raise WorkflowError("write not found after recovery; manual review required")
        rendered = self._render(record)
        if self.gateway.read_back(plan_id) != rendered:
            record["status"] = "READBACK_FAILED"
            self.store.write(state)
            raise WorkflowError("reconciled write failed read-back")
        record.update({"status": "SUCCESS", "reference": f"mock://contracts/{plan_id}"})
        self.store.write(state)
        return {"status": "RECOVERED_SUCCESS", "reference": record["reference"]}

    def _fetch_with_retry(self, target: Target) -> Snapshot:
        for attempt in range(3):
            try:
                return self.gateway.fetch(target)
            except TransientReadError:
                if attempt == 2:
                    raise WorkflowError("read retry limit reached") from None
                sleep(0.01)
            except NonRetryableReadError:
                raise WorkflowError("non-retryable read failure") from None
        raise AssertionError("unreachable")

    def _validate_snapshot(self, target: Target, snapshot: Snapshot, max_lines: int, ttl_seconds: int) -> None:
        if snapshot.target != target:
            raise WorkflowError("snapshot target mismatch")
        if snapshot.schema_version != 1:
            raise WorkflowError("schema incompatible")
        if self.now() - snapshot.captured_at > timedelta(seconds=ttl_seconds):
            raise WorkflowError("snapshot expired")
        if not snapshot.lines or len(snapshot.lines) > max_lines:
            raise WorkflowError("blast radius limit exceeded")
        keys = [line.external_id for line in snapshot.lines]
        if any(not key for key in keys) or len(keys) != len(set(keys)):
            raise WorkflowError("missing or duplicate primary key")
        if any(line.quantity <= 0 or line.amount < Decimal("0") for line in snapshot.lines):
            raise WorkflowError("invalid line values")

    @staticmethod
    def _serialise_plan(plan: Plan) -> dict:
        return {
            "target": asdict(plan.target), "snapshot_id": plan.snapshot_id, "created_at": plan.created_at.isoformat(),
            "digest": plan.digest, "status": "PREVIEW", "lines": [
                {"external_id": line.external_id, "item_name": line.item_name, "quantity": line.quantity, "amount": str(line.amount)} for line in plan.lines
            ],
        }

    @staticmethod
    def _render(record: dict) -> str:
        total = sum(Decimal(item["amount"]) for item in record["lines"])
        return f"REFERENCE CONTRACT|{record['target']['supplier_key']}|{record['target']['period']}|{total:.2f}|{record['digest']}"
