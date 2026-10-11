# Testing

Run:

```bash
python -m unittest discover -s tests -v
```

The public suite covers successful execution, idempotent duplicates, missing/duplicate primary keys, target mismatch, incompatible schema, stale snapshot, blast-radius limit, transient and non-retryable reads, unknown writes, read-back mismatch, crash recovery, lease competition, and HTTP health.

The test count reported by this repository is its own offline test count. It does not reuse or represent any production test metric.
