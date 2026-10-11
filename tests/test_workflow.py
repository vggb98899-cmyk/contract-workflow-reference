from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from contract_workflow.domain import ContractLine, Snapshot, Target
from contract_workflow.engine import ContractWorkflow, WorkflowError
from contract_workflow.mock_gateway import MockProcurementGateway
from contract_workflow.scheduler import InMemoryLeaseRegistry
from contract_workflow.store import JsonStore


class FixedSnapshotGateway(MockProcurementGateway):
    def __init__(self, snapshot: Snapshot) -> None:
        super().__init__([])
        self.snapshot = snapshot

    def fetch(self, target: Target) -> Snapshot:
        return self.snapshot


class WorkflowTests(unittest.TestCase):
    target = Target("supplier-alpha", "2026-06")

    def setUp(self) -> None:
        self.temp_directories: list[TemporaryDirectory] = []

    def make_workflow(self, records=None, failures=(), gateway=None, now=None):
        temporary = TemporaryDirectory()
        self.temp_directories.append(temporary)
        source = gateway or MockProcurementGateway(records or MockProcurementGateway.example_records(), failures)
        return ContractWorkflow(source, JsonStore(Path(temporary.name) / "state.json"), now), source

    def tearDown(self) -> None:
        for temporary in self.temp_directories:
            temporary.cleanup()

    def test_success_and_idempotent_duplicate_call(self):
        workflow, _ = self.make_workflow()
        plan = workflow.preview(self.target)
        self.assertEqual(workflow.execute(plan.plan_id, self.target)["status"], "SUCCESS")
        self.assertEqual(workflow.execute(plan.plan_id, self.target)["status"], "IDEMPOTENT_SUCCESS")

    def test_missing_or_duplicate_primary_key_is_rejected(self):
        for external_id in ("", "PO-1"):
            records = [
                {"supplier_key": "supplier-alpha", "period": "2026-06", "external_id": external_id, "item_name": "A", "quantity": 1, "amount": "1.00"},
                {"supplier_key": "supplier-alpha", "period": "2026-06", "external_id": "PO-1", "item_name": "B", "quantity": 1, "amount": "1.00"},
            ]
            workflow, _ = self.make_workflow(records)
            with self.assertRaisesRegex(WorkflowError, "primary key"):
                workflow.preview(self.target)

    def test_target_mismatch_is_fail_closed(self):
        workflow, _ = self.make_workflow()
        plan = workflow.preview(self.target)
        with self.assertRaisesRegex(WorkflowError, "target mismatch"):
            workflow.execute(plan.plan_id, Target("supplier-beta", "2026-06"))

    def test_schema_incompatible_and_expired_snapshot_are_rejected(self):
        old = Snapshot("old", self.target, datetime.now(timezone.utc) - timedelta(minutes=10), 1, (ContractLine("A", "item", 1, Decimal("1")),))
        workflow, _ = self.make_workflow(gateway=FixedSnapshotGateway(old))
        with self.assertRaisesRegex(WorkflowError, "expired"):
            workflow.preview(self.target, snapshot_ttl_seconds=1)
        bad = Snapshot("bad", self.target, datetime.now(timezone.utc), 2, old.lines)
        workflow, _ = self.make_workflow(gateway=FixedSnapshotGateway(bad))
        with self.assertRaisesRegex(WorkflowError, "schema"):
            workflow.preview(self.target)

    def test_blast_radius_limit(self):
        workflow, _ = self.make_workflow()
        with self.assertRaisesRegex(WorkflowError, "blast radius"):
            workflow.preview(self.target, max_lines=1)

    def test_transient_read_retries_but_nonretryable_stops(self):
        workflow, _ = self.make_workflow(failures=["transient_read", "transient_read"])
        self.assertTrue(workflow.preview(self.target).plan_id.startswith("plan-"))
        workflow, _ = self.make_workflow(failures=["nonretryable_read"])
        with self.assertRaisesRegex(WorkflowError, "non-retryable"):
            workflow.preview(self.target)

    def test_unknown_write_blocks_duplicate_and_recovery_reconciles(self):
        workflow, _ = self.make_workflow(failures=["unknown_write"])
        plan = workflow.preview(self.target)
        with self.assertRaisesRegex(WorkflowError, "unknown write"):
            workflow.execute(plan.plan_id, self.target)
        with self.assertRaisesRegex(WorkflowError, "unknown prior"):
            workflow.execute(plan.plan_id, self.target)
        self.assertEqual(workflow.recover(plan.plan_id)["status"], "RECOVERED_SUCCESS")

    def test_readback_mismatch_fails(self):
        workflow, _ = self.make_workflow(failures=["readback_mismatch"])
        plan = workflow.preview(self.target)
        with self.assertRaisesRegex(WorkflowError, "read-back mismatch"):
            workflow.execute(plan.plan_id, self.target)

    def test_crash_recovery_reconciles_prepared_state(self):
        workflow, gateway = self.make_workflow()
        plan = workflow.preview(self.target)
        state = workflow.store.read()
        state["plans"][plan.plan_id]["status"] = "PREPARED"
        workflow.store.write(state)
        gateway.writes[plan.plan_id] = {"rendered": workflow._render(state["plans"][plan.plan_id]), "readback": workflow._render(state["plans"][plan.plan_id])}
        self.assertEqual(workflow.recover(plan.plan_id)["status"], "RECOVERED_SUCCESS")

    def test_scheduler_lease_competition(self):
        registry = InMemoryLeaseRegistry()
        self.assertTrue(registry.acquire("daily-run", "worker-a", 60))
        self.assertFalse(registry.acquire("daily-run", "worker-b", 60))
        registry.release("daily-run", "worker-a")
        self.assertTrue(registry.acquire("daily-run", "worker-b", 60))


if __name__ == "__main__":
    unittest.main()
