# 99designs Contest Collector

Collects the public `The Brief` payload and the displayed Winner image for
completed contests from the configured 99designs listing.

## Permission boundary

99designs' current terms prohibit unauthorized automated scraping, and the
target filtered listing is disallowed by the site's current `robots.txt` rules.
Use this collector only after obtaining written permission from 99designs.

The collector deliberately:

- requires a local authorization note before any crawl;
- identifies itself with a contact email;
- enforces at least two seconds between requests;
- stops on ordinary access failures and respects `429` backoff;
- does not log in, rotate IPs, solve CAPTCHAs, or call `/brief`/internal APIs;
- downloads only the public Winner rendition exposed on the contest page;
- records `rights.status=permission_required` because the original Winner
  transfer does not give Curify reuse, redistribution, or model-training rights.

Terms: <https://99designs.com/legal/terms-and-conditions>

Robots: <https://99designs.hk/robots.txt>

## Authorization note

Create a file outside Git containing at least:

```text
AUTHORIZED_BY=<99designs contact or agreement reference>
SCOPE=<approved domains, fields, volume, image use and retention>
DATE=<YYYY-MM-DD>
```

Do not commit the authorization note. The output stores only its SHA-256
fingerprint, not the note contents.

## Run

Create a small virtual environment first. `certifi` supplies a current CA bundle
for Python installations that do not use the macOS system certificate store:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

First inspect the intended run:

```bash
.venv/bin/python collect.py \
  --authorization-file /absolute/path/to/99designs-permission.txt \
  --contact-email research@example.com \
  --dry-run
```

Collect five contests with briefs and Winner images:

```bash
.venv/bin/python collect.py \
  --authorization-file /absolute/path/to/99designs-permission.txt \
  --contact-email research@example.com \
  --max-pages 2 \
  --max-contests 5 \
  --download-images \
  --output-dir output
```

The default listing is the requested Art & Design / Won / newest-first URL:

```text
https://99designs.hk/contests?industry=art&sort=start-date%3Adesc&status=won&entry-level=0&mid-level=0&top-level=0&dir=desc&order=start-date
```

The command is resumable: existing `source_url` values in `contests.jsonl` are
skipped on subsequent runs.

## Output

```text
output/
├── contests.jsonl
├── discovered-urls.txt
├── failures.jsonl
├── run-summary.json
└── images/
    └── <contest-id>/
        └── winner-01.<ext>
```

Each JSONL record includes the structured Brief fields, a flattened Brief text,
contest/category metadata, Winner/designer metadata, source URL, image hash and
an explicit rights manifest.

## Search-index metadata pilot

`search-index-pilot-v0.1.jsonl` is a separate, deliberately restricted pilot.
It was assembled from search-engine-indexed public metadata without requesting
the disallowed filtered listing, downloading images, or copying complete Briefs.

The pilot contains only source URLs, contest identifiers, titles, categories,
short paraphrased Brief summaries, counts exposed by the search index, and
Winner names when the search index made them verifiable. Missing Winner fields
remain explicitly `unverified`; they are never inferred.

Every record is fixed to `rights.status=metadata_only` and asserts that no full
Brief, Winner image URL, image pixels, training permission, or redistribution
permission is present. It is an evaluation/reference index, not a training set.

Validate it with:

```bash
python3 validate_metadata_index.py search-index-pilot-v0.1.jsonl
```

## Test

Tests use synthetic HTML only and make no network requests:

```bash
.venv/bin/python -m unittest -v test_collect.py
```
