#!/usr/bin/env python3
"""Validate real-pixel query bindings and write a compact Markdown report."""
from __future__ import annotations

from pathlib import Path

from reference_assets import validate_pack


HERE = Path(__file__).resolve().parent
OUT = HERE / "reference_asset_eval.md"


def main() -> int:
    result = validate_pack()
    mib = result["total_bytes"] / (1024 * 1024)
    status = "PASS" if result["ok"] else "FAIL"
    lines = [
        "# Reference asset eval — reference-pack-v0.1",
        "",
        f"- **status:** {status}",
        f"- **required multimodal queries bound:** {result['bound_queries']}/{result['required_queries']}",
        f"- **layers:** {result['layer_counts']}",
        f"- **asset bindings:** {result['asset_bindings']}",
        f"- **unique manifest assets used:** {result['used_assets']}/{result['unique_assets']}",
        f"- **decoded payload:** {mib:.2f} MiB",
        f"- **transparent assets:** {result['transparent_assets']}",
        f"- **synthetic-person assets:** {result['synthetic_person_assets']}",
        f"- **assets containing personal data:** {result['personal_data_assets']}",
        "",
        "Checks: JSONL parsing, query coverage, manifest resolution, path containment, file presence, "
        "SHA-256, byte size, image decoding, dimensions/mode, and alpha-corner integrity.",
    ]
    if result["errors"]:
        lines += ["", "## Errors", ""] + [f"- {error}" for error in result["errors"]]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{status}: {result['bound_queries']}/{result['required_queries']} queries; "
          f"{result['used_assets']}/{result['unique_assets']} assets; report -> {OUT}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
