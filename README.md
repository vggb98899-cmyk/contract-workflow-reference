# Reliable Contract Workflow Reference

An offline, production-grade reference implementation for a safe document workflow: **read a bounded snapshot → preview an immutable plan → execute once → read back → reconcile uncertain outcomes**.

> **Public reference implementation, not production source code.** This repository was independently reimplemented for portfolio use. It contains only synthetic records and a mock external gateway. It does not include any employer system, vendor, customer, ERP endpoint, browser automation, production template, credential, runtime state, or business data.

## The engineering problem

Document automation is not merely “create a file.” A production workflow must defend against wrong targets, schema drift, stale snapshots, duplicate writes, partial failures, and crashes that make the previous write result unknown. This project demonstrates those controls in a small, inspectable system.

## Architecture

```text
Mock procurement gateway (synthetic data)
                │ bounded retry for read-only work
                ▼
        Snapshot validation gate
  target · schema · primary key · TTL · blast radius
                ▼
      Immutable preview / execution plan
                ▼
   Idempotency ledger (atomic JSON state)
                ▼
       Mock write → mandatory read-back
                ▼
 Success / UNKNOWN / read-back failure / recovery
```

See [docs/architecture.md](docs/architecture.md), [docs/decisions.md](docs/decisions.md), [docs/testing.md](docs/testing.md), and [docs/failure-handling.md](docs/failure-handling.md).

## Key mechanisms

- Fail-closed target, schema, primary-key, TTL, and blast-radius gates.
- Immutable digest-bound plans: preview data is persisted before a write is attempted.
- Idempotency: a successful plan returns the same result on repeated execution.
- Unknown-write protection: an uncertain write cannot be retried blindly.
- Read-back verification after write, plus reconciliation-based crash recovery.
- Bounded retry only for transient read failures; non-retryable errors stop immediately.
- Scheduler lease competition example and a dependency-free health endpoint.

## Run locally

Requires Python 3.10+ and no third-party packages.

```bash
python -m unittest discover -s tests -v
python -m contract_workflow.app
```

Then visit `http://127.0.0.1:8240/health`.

## Example result

```text
SUCCESS: plan is written and verified by read-back
IDEMPOTENT_SUCCESS: the same plan is never written twice
RECOVERED_SUCCESS: an interrupted/unknown write is reconciled before completion
```

## Production experience vs. this repository

The author has applied these kinds of reliability controls in real workflow automation. This repository deliberately shows an **independent, generic reference design** only. Its gateway, records, contract rendering, state storage, and endpoint are all mock or synthetic. Enterprise-specific mappings, systems, data, credentials, templates, deployment, and source code are intentionally not published.

## Interviewer reading route

1. Read the architecture and decisions documents.
2. Start with `contract_workflow/engine.py` for the failure boundaries.
3. Read `tests/test_workflow.py` to see each gate exercised.
4. Run the offline test suite and inspect `mock_gateway.py`.

## Known limitations

- The JSON state store is intentionally local and single-process; production would use a transactional shared store.
- The mock gateway demonstrates semantics, not a real network protocol.
- The health endpoint demonstrates liveness only; it is not an authentication layer.

## Stack

Python standard library, `unittest`, atomic file replacement, HTTP server, dataclasses, and deterministic JSON digests.

## License

[MIT](LICENSE)
