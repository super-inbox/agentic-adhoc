# Excluded harness-development canary

The `invalid-schema-uniqueitems/` directory preserves three zero-inference
requests rejected with HTTP 400 before model execution. The first draft used
the unsupported JSON Schema keyword `uniqueItems`.

These requests are excluded from the formal `runs/`, run index, reliability
metrics, and frozen baseline because they test a broken harness rather than the
candidate model. After removing that keyword, all three canaries and all 118
formal cases completed on their first actual inference attempt.
