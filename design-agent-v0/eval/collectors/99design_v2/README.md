# 99designs public contest reference samples v0.2

This directory contains manually inspected, self-contained reference samples
from completed public 99designs contest pages.

## Coverage

| Collection | Contests | Public previews | Structure |
|---|---:|---:|---|
| `Art Design/` | 9 | 44 | 1 Winner + up to 4 visible candidates |
| `Travel Hotel/` | 10 | 50 | 1 Winner + 4 visible candidates |
| `Logo_identity/` | 6 | 30 | 1 Winner + 4 visible candidates |
| `Web_app/` | 6 | 30 | 1 Winner + 4 visible candidates |
| `Business/` | 6 | 30 | 1 Winner + 4 visible candidates |
| `clothing/` | 6 | 30 | 1 Winner + 4 visible candidates |
| `Art/` | 6 | 30 | 1 Winner + 4 visible candidates |
| `packaging/` | 6 | 30 | 1 Winner + 4 visible candidates |
| `book/` | 6 | 30 | 1 Winner + 4 visible candidates |
| **Total** | **61** | **304** | partial Brief + selection metadata + images |

Each contest directory contains:

- `contest-<id>.json`: source, partial public Brief, contest statistics,
  Winner/candidate metadata, image hashes, evaluation semantics and rights;
- `README.md`: a human-readable summary;
- public 500x500 preview renditions referenced by the JSON record.

Each collection also contains its manually selected source manifest, a
materialization summary, and an idempotent preview materializer. The scripts do
not discover or crawl contest pages; they only fetch the explicit public image
URLs captured during manual page inspection.

## Evaluation semantics

The selected Winner can be compared with the visible non-winning candidates
for retrieval, ranking and pairwise preference experiments. A non-winner label
means only "not selected in this contest". It does not mean the design is
objectively poor, and the public page does not provide an individual rejection
reason or confirm that a displayed candidate was a finalist.

The public Brief may contain ellipses, and referenced input attachments,
private comments, revisions and production source files are generally absent.
Do not reconstruct or invent missing fields.

## Rights boundary

Public visibility does not establish permission for model training or
redistribution. Every contest record therefore sets:

```json
{
  "rights": {
    "status": "permission_required",
    "training_use": "not_cleared",
    "redistribution": "not_cleared"
  }
}
```

Treat this as an evaluation/reference snapshot pending a documented rights
review. The metadata must not be interpreted as a license from 99designs, the
contest clients or the designers.
