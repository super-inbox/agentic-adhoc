#!/usr/bin/env python3
"""Start a capture file. One command, so beginning costs nothing.

Friction is the only thing that kills this dataset, so this does the naming,
dating and prefilling. Everything after is editing one file as the project
happens.
"""
from __future__ import annotations
import argparse, json, sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", required=True, help="pseudonymous id, e.g. client-004")
    ap.add_argument("--category", required=True)
    ap.add_argument("--intent", default="generate")
    ap.add_argument("--date", default=date.today().isoformat(),
                    help="ISO date; defaults to today")
    a = ap.parse_args()

    if not a.client.startswith("client-"):
        print("client id must be pseudonymous and look like client-004 — "
              "never a real name", file=sys.stderr)
        return 2

    tpl = json.loads((HERE / "TEMPLATE.json").read_text(encoding="utf-8"))
    slug = a.category.split("_")[0]
    pid = f"{a.date}-{a.client}-{slug}"
    tpl.update({"project_id": pid, "client_id": a.client,
                "category": a.category, "primary_intent": a.intent})

    out = HERE / "projects" / f"{pid}.json"
    out.parent.mkdir(exist_ok=True)
    if out.exists():
        print(f"exists already: {out.relative_to(HERE)}", file=sys.stderr)
        return 1
    out.write_text(json.dumps(tpl, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(f"created {out.relative_to(HERE)}")
    print("\nCapture as it happens — the four moments in README.md:")
    print("  1 brief arrives    -> initial_query, VERBATIM")
    print("  2 options shown    -> alternatives, including the losers")
    print("  3 they choose      -> selection + rejections[].reason_verbatim")
    print("  4 revision asked   -> feedback[].message, VERBATIM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
