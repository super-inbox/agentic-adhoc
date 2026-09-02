# 99designs references organized by design type — v3

This is a lossless design-type reclassification of `../99design_v2`.
The v2 source tree remains unchanged. Every contest keeps its Brief,
Winner/non-winner semantics, source metadata and rights fields.

## Structure

```text
99design_v3/
└── <Design Type>/
    └── <Subtype>/
        └── <Contest Title>/
            ├── contest-<id>.json
            ├── README.md
            └── <public preview images>
```

## Coverage

| Design type | Contests | Images |
|---|---:|---:|
| Brand Design | 14 | 70 |
| Banner Design | 9 | 44 |
| Web & App Design | 6 | 30 |
| Packaging & Label Design | 6 | 30 |
| Print & Editorial Design | 12 | 60 |
| Art & Illustration Design | 5 | 25 |
| Merchandise Design | 6 | 30 |
| Environmental & Signage Design | 3 | 15 |
| **Total** | **61** | **304** |

## Files

- `taxonomy-v0.1.json`: complete 21-category mapping and counts;
- `index-v0.1.jsonl`: one searchable row per contest;
- `reclassification-summary-v0.1.json`: readable full summary;
- `reclassify_by_design_type.py`: idempotent local materializer.

Each copied contest JSON adds `classification_v3`; all original
fields remain intact. Image bytes and SHA256 values are unchanged.

## Rights boundary

This operation only changes organization. Public visibility does
not establish permission for model training or redistribution.
The original `rights` object remains authoritative.
