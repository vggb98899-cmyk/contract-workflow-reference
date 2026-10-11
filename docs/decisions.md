# Design decisions

| Decision | Rationale |
|---|---|
| Preview before write | Separates acquisition/validation from side effects. |
| Plan digest | Makes the execution payload deterministic and auditable. |
| Fail closed on mismatch | Wrong target/schema/key data is more dangerous than a stopped job. |
| No automatic retry after unknown write | A duplicate external document is worse than requiring reconciliation. |
| Read-back after every write | A successful transport response does not prove correct persistence. |
| Bounded read retry | Read-only transient work can retry; invalid input cannot be repaired by retrying. |
| Lease registry | Demonstrates that scheduled workers must contend safely. |

This is an independent reference design. It does not claim to expose or reproduce any enterprise implementation.
