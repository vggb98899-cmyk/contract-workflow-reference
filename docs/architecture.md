# Architecture

The reference separates the workflow into four explicit boundaries:

1. **Gateway** – a synthetic external-system adapter. Only read-only acquisition retries.
2. **Validation** – checks target identity, schema version, unique primary keys, freshness, valid numeric values, and blast radius before a plan exists.
3. **Plan and ledger** – serializes a digest-bound immutable plan and tracks `PREVIEW`, `PREPARED`, `UNKNOWN`, `READBACK_FAILED`, and `SUCCESS` states atomically.
4. **Execution** – performs exactly one write attempt, requires read-back, and uses reconciliation rather than repeating an uncertain write.

The public implementation intentionally uses a local JSON ledger to make every state transition easy to inspect. The design maps naturally to a database transaction or durable queue in a production deployment.
