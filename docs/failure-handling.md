# Failure handling

| Failure | Behaviour |
|---|---|
| Transient read | Retry at most twice, then fail. |
| Non-retryable read | Fail immediately. |
| Target/schema/key/TTL/blast-radius issue | Fail before plan persistence or write. |
| Unknown write outcome | Mark `UNKNOWN`; block repeat writes; reconcile first. |
| Read-back mismatch | Mark `READBACK_FAILED`; stop. |
| Crash after prepare | Reconcile the external side effect and require matching read-back. |
| Scheduler race | One lease owner wins; competitors must defer. |
