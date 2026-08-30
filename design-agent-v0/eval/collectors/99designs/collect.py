#!/usr/bin/env python3
"""Collect public 99designs contest briefs and displayed winner images.

This collector is intentionally permission-gated. 99designs' published terms and
robots rules restrict automated collection, so network crawling requires a local
authorization note. The program does not log in, solve CAPTCHAs, rotate proxies,
or call private/internal endpoints.
"""

from __future__ import annotations

import argparse
import hashlib
import html
from html.parser import HTMLParser
import json
import mimetypes
import os
from pathlib import Path
import random
import re
import ssl
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import Message
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPSHandler, Request, build_opener


DEFAULT_LIST_URL = (
    "https://99designs.hk/contests?industry=art&sort=start-date%3Adesc"
    "&status=won&entry-level=0&mid-level=0&top-level=0&dir=desc"
    "&order=start-date"
)
TERMS_URL = "https://99designs.com/legal/terms-and-conditions"
ROBOTS_URL = "https://99designs.hk/robots.txt"
MIN_DELAY_SECONDS = 2.0
MAX_HTML_BYTES = 20 * 1024 * 1024
MAX_IMAGE_BYTES = 30 * 1024 * 1024
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
CONTEST_PATH_RE = re.compile(r"^/[^/]+/contests/[^/?#]+-\d+/?$")


class CollectionError(RuntimeError):
    """Raised for an expected collection or extraction failure."""


@dataclass(frozen=True)
class Authorization:
    fingerprint: str
    source_path: str


@dataclass(frozen=True)
class FetchResult:
    url: str
    body: bytes
    headers: Message
    status: int

    def text(self) -> str:
        charset = self.headers.get_content_charset() or "utf-8"
        return self.body.decode(charset, errors="replace")


@dataclass(frozen=True)
class RobotsRule:
    allow: bool
    pattern: str

    @property
    def specificity(self) -> int:
        return len(self.pattern.replace("*", "").replace("$", ""))

    def matches(self, path_with_query: str) -> bool:
        if not self.pattern:
            return False
        end_anchored = self.pattern.endswith("$")
        pattern = self.pattern[:-1] if end_anchored else self.pattern
        regex = "^" + re.escape(pattern).replace(r"\*", ".*")
        if end_anchored:
            regex += "$"
        return re.search(regex, path_with_query) is not None


class RobotsPolicy:
    """Small robots.txt parser with support for '*' and '$' path patterns."""

    def __init__(self, groups: Sequence[Tuple[Sequence[str], Sequence[RobotsRule]]]):
        self.groups = list(groups)

    @classmethod
    def parse(cls, text: str) -> "RobotsPolicy":
        groups: List[Tuple[List[str], List[RobotsRule]]] = []
        agents: List[str] = []
        rules: List[RobotsRule] = []

        def flush() -> None:
            nonlocal agents, rules
            if agents:
                groups.append((agents, rules))
            agents, rules = [], []

        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, value = (part.strip() for part in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if rules:
                    flush()
                agents.append(value.lower())
            elif key in {"allow", "disallow"} and agents:
                if value or key == "allow":
                    rules.append(RobotsRule(allow=key == "allow", pattern=value))
        flush()
        return cls(groups)

    def can_fetch(self, user_agent: str, url: str) -> bool:
        token = user_agent.split("/", 1)[0].lower()
        exact: List[RobotsRule] = []
        wildcard: List[RobotsRule] = []
        for agents, rules in self.groups:
            if any(agent != "*" and agent in token for agent in agents):
                exact.extend(rules)
            if "*" in agents:
                wildcard.extend(rules)
        applicable = exact or wildcard
        parsed = urlsplit(url)
        target = parsed.path or "/"
        if parsed.query:
            target += "?" + parsed.query
        matches = [rule for rule in applicable if rule.matches(target)]
        if not matches:
            return True
        winner = max(matches, key=lambda rule: (rule.specificity, rule.allow))
        return winner.allow


class LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag.lower() != "a":
            return
        values = dict(attrs)
        href = values.get("href")
        if href:
            self.hrefs.append(href)


class NextDataExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._capturing = False
        self._parts: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag.lower() == "script" and dict(attrs).get("id") == "__NEXT_DATA__":
            self._capturing = True

    def handle_data(self, data: str) -> None:
        if self._capturing:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._capturing:
            self._capturing = False

    @property
    def json_text(self) -> str:
        return "".join(self._parts).strip()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ssl_context() -> ssl.SSLContext:
    cafile = os.environ.get("SSL_CERT_FILE")
    if cafile:
        return ssl.create_default_context(cafile=cafile)
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


class PoliteClient:
    def __init__(
        self,
        user_agent: str,
        delay_seconds: float,
        timeout_seconds: float,
        max_retries: int,
    ) -> None:
        if delay_seconds < MIN_DELAY_SECONDS:
            raise ValueError(f"delay must be at least {MIN_DELAY_SECONDS:.1f} seconds")
        self.user_agent = user_agent
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._last_request_at = 0.0
        self._ssl_context = ssl_context()
        self._opener = build_opener(HTTPSHandler(context=self._ssl_context))

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait_for = self.delay_seconds - elapsed
        if wait_for > 0:
            time.sleep(wait_for + random.uniform(0.0, 0.35))

    def get(self, url: str, *, max_bytes: int, accept: str) -> FetchResult:
        last_error: Optional[BaseException] = None
        for attempt in range(self.max_retries + 1):
            self._wait()
            request = Request(
                url,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": accept,
                    "Accept-Encoding": "identity",
                },
            )
            try:
                self._last_request_at = time.monotonic()
                with self._opener.open(request, timeout=self.timeout_seconds) as response:
                    content_length = response.headers.get("Content-Length")
                    if content_length and int(content_length) > max_bytes:
                        raise CollectionError(
                            f"response exceeds {max_bytes} bytes: {response.geturl()}"
                        )
                    body = response.read(max_bytes + 1)
                    if len(body) > max_bytes:
                        raise CollectionError(
                            f"response exceeds {max_bytes} bytes: {response.geturl()}"
                        )
                    return FetchResult(
                        url=response.geturl(),
                        body=body,
                        headers=response.headers,
                        status=response.status,
                    )
            except HTTPError as exc:
                last_error = exc
                if exc.code not in RETRYABLE_STATUS or attempt >= self.max_retries:
                    break
                retry_after = exc.headers.get("Retry-After")
                wait_for = float(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
                time.sleep(max(wait_for, self.delay_seconds))
            except URLError as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(max(2 ** attempt, self.delay_seconds))
        raise CollectionError(f"request failed for {url}: {last_error}")


def read_authorization(path: Optional[Path]) -> Authorization:
    if path is None:
        raise CollectionError(
            "network collection is disabled without --authorization-file; "
            "obtain written permission from 99designs first"
        )
    if not path.is_file():
        raise CollectionError(f"authorization file not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    required = ("AUTHORIZED_BY=", "SCOPE=", "DATE=")
    missing = [key for key in required if key not in text]
    if missing:
        raise CollectionError(
            "authorization file must document " + ", ".join(missing)
        )
    return Authorization(
        fingerprint=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        source_path=str(path.resolve()),
    )


def page_url(list_url: str, page: int) -> str:
    parsed = urlsplit(list_url)
    query = [(key, value) for key, value in parse_qsl(parsed.query) if key != "page"]
    if page > 1:
        query.append(("page", str(page)))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))


def contest_urls_from_html(document: str, base_url: str) -> List[str]:
    parser = LinkExtractor()
    parser.feed(document)
    host = urlsplit(base_url).netloc.lower()
    found: Set[str] = set()
    for href in parser.hrefs:
        absolute = urljoin(base_url, html.unescape(href))
        parsed = urlsplit(absolute)
        if parsed.netloc.lower() != host or not CONTEST_PATH_RE.match(parsed.path):
            continue
        found.add(urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", "")))
    return sorted(found)


def next_data_from_html(document: str) -> Dict[str, Any]:
    parser = NextDataExtractor()
    parser.feed(document)
    if not parser.json_text:
        raise CollectionError("contest page does not contain __NEXT_DATA__")
    try:
        value = json.loads(parser.json_text)
    except json.JSONDecodeError as exc:
        raise CollectionError(f"invalid __NEXT_DATA__: {exc}") from exc
    if not isinstance(value, dict):
        raise CollectionError("__NEXT_DATA__ root is not an object")
    return value


def selected_choice(element: Dict[str, Any], key: str) -> Any:
    selected = element.get(key)
    choices = element.get("choices") or []
    if isinstance(selected, list):
        selected_keys = {
            item.get("key") if isinstance(item, dict) else item for item in selected
        }
        return [
            simplify_choice(choice)
            for choice in choices
            if choice.get("key") in selected_keys
        ] or list(selected_keys)
    for choice in choices:
        if choice.get("key") == selected:
            return simplify_choice(choice)
    return selected


def simplify_choice(choice: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in choice.items()
        if key in {"key", "value", "label", "description", "url"} and value not in (None, "")
    }


def normalize_brief_element(element: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {
        "key": element.get("key"),
        "title": element.get("title"),
        "type": str(element.get("__typename", "")).removeprefix("ContestOverview"),
    }
    if "textValue" in element:
        normalized["value"] = element.get("textValue", "")
    elif "textAreaValue" in element:
        normalized["value"] = element.get("textAreaValue", "")
    elif "choiceValue" in element:
        normalized["value"] = selected_choice(element, "choiceValue")
    elif "multiChoiceImgValue" in element:
        normalized["value"] = selected_choice(element, "multiChoiceImgValue")
    elif "sliders" in element:
        normalized["value"] = [
            {
                key: slider.get(key)
                for key in ("key", "min", "max", "value")
                if slider.get(key) is not None
            }
            for slider in element.get("sliders", [])
        ]
    elif "urls" in element:
        normalized["value"] = list(element.get("urls") or [])
    else:
        normalized["value"] = {
            key: value
            for key, value in element.items()
            if key not in {"__typename", "key", "title", "choices"}
        }
    return normalized


def brief_as_text(fields: Sequence[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for field in fields:
        value = field.get("value")
        if value in (None, "", [], {}):
            continue
        if isinstance(value, str):
            rendered = " ".join(value.split())
        else:
            rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        lines.append(f"{field.get('title') or field.get('key')}: {rendered}")
    return "\n".join(lines)


def extract_contest(document: str, source_url: str, authorization: Authorization) -> Dict[str, Any]:
    data = next_data_from_html(document)
    try:
        contest = data["props"]["pageProps"]["contestOverviewResult"]["resp"]
    except (KeyError, TypeError) as exc:
        raise CollectionError("contest overview payload not found") from exc
    if not isinstance(contest, dict):
        raise CollectionError("contest overview payload is not an object")
    if contest.get("isUnlisted") or contest.get("isRobotsNoIndex"):
        raise CollectionError("contest is unlisted or marked noindex")
    if not contest.get("isCompleted"):
        raise CollectionError("contest is not completed")
    winning_entries = contest.get("winningEntries") or []
    if not winning_entries:
        raise CollectionError("contest has no public winning entry")

    brief_elements = ((contest.get("brief") or {}).get("elements") or [])
    brief_fields = [
        normalize_brief_element(element)
        for element in brief_elements
        if isinstance(element, dict)
    ]
    winners: List[Dict[str, Any]] = []
    for index, entry in enumerate(winning_entries, start=1):
        designer = entry.get("designer") or {}
        user = designer.get("user") or {}
        image_url = entry.get("designUrl")
        if not image_url:
            continue
        winners.append(
            {
                "winner_index": index,
                "designer_id": designer.get("id"),
                "designer_name": user.get("displayName"),
                "designer_level": designer.get("designerLevel"),
                "image_url": image_url,
                "local_path": None,
                "sha256": None,
            }
        )
    if not winners:
        raise CollectionError("winning entry has no displayed image URL")

    industry = contest.get("industry") or {}
    category = contest.get("category") or {}
    industry_key = industry.get("key")
    if not industry_key:
        for field in brief_fields:
            if field.get("key") == "industry":
                value = field.get("value")
                industry_key = value.get("key") if isinstance(value, dict) else value
                break

    return {
        "schema_version": "99designs-contest-reference-v0.1",
        "source": "99designs",
        "source_url": source_url,
        "retrieved_at": utc_now(),
        "contest_id": str(contest.get("id") or ""),
        "title": contest.get("title"),
        "category": {
            "key": category.get("key"),
            "title": category.get("title"),
        },
        "industry": {
            "key": industry_key,
            "title": industry.get("title"),
        },
        "entry_count": contest.get("entryCount"),
        "designer_count": contest.get("designerCount"),
        "winning_entry_count": contest.get("winningEntryCount"),
        "deliverable_file_types": contest.get("deliverableFileTypes") or [],
        "brief": {
            "fields": brief_fields,
            "text": brief_as_text(brief_fields),
        },
        "winners": winners,
        "rights": {
            "status": "permission_required",
            "authorization_fingerprint": authorization.fingerprint,
            "terms_url": TERMS_URL,
            "notice": (
                "The winner transfer applies to the original contest client; "
                "it does not grant this collector training or redistribution rights."
            ),
        },
    }


def extension_for_image(content_type: str, url: str) -> str:
    media_type = content_type.split(";", 1)[0].strip().lower()
    known = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/avif": ".avif",
    }
    if media_type in known:
        return known[media_type]
    guessed = mimetypes.guess_extension(media_type) or Path(urlsplit(url).path).suffix
    return guessed if guessed and len(guessed) <= 6 else ".img"


def download_winners(
    client: PoliteClient,
    record: Dict[str, Any],
    output_dir: Path,
) -> None:
    contest_dir = output_dir / "images" / record["contest_id"]
    contest_dir.mkdir(parents=True, exist_ok=True)
    for winner in record["winners"]:
        result = client.get(
            winner["image_url"],
            max_bytes=MAX_IMAGE_BYTES,
            accept="image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8",
        )
        content_type = result.headers.get_content_type()
        if not content_type.startswith("image/"):
            raise CollectionError(
                f"winner URL returned non-image content ({content_type})"
            )
        digest = hashlib.sha256(result.body).hexdigest()
        extension = extension_for_image(content_type, result.url)
        filename = f"winner-{winner['winner_index']:02d}{extension}"
        destination = contest_dir / filename
        destination.write_bytes(result.body)
        winner["local_path"] = str(destination.relative_to(output_dir))
        winner["sha256"] = digest
        winner["content_type"] = content_type
        winner["bytes"] = len(result.body)


def append_jsonl(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def completed_urls(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    urls: Set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CollectionError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
            source_url = value.get("source_url")
            if source_url:
                urls.add(source_url)
    return urls


def discover_urls(
    client: PoliteClient,
    list_url: str,
    max_pages: int,
) -> List[str]:
    discovered: List[str] = []
    seen: Set[str] = set()
    for page in range(1, max_pages + 1):
        current_url = page_url(list_url, page)
        result = client.get(
            current_url,
            max_bytes=MAX_HTML_BYTES,
            accept="text/html,application/xhtml+xml",
        )
        page_urls = contest_urls_from_html(result.text(), result.url)
        if not page_urls:
            break
        added = 0
        for url in page_urls:
            if url not in seen:
                seen.add(url)
                discovered.append(url)
                added += 1
        if added == 0:
            break
    return discovered


def write_run_summary(output_dir: Path, summary: Dict[str, Any]) -> None:
    path = output_dir / "run-summary.json"
    path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Permission-gated collector for public 99designs contest briefs and winners."
    )
    parser.add_argument("--list-url", default=DEFAULT_LIST_URL)
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--authorization-file", type=Path, required=True)
    parser.add_argument("--contact-email", required=True)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--max-contests", type=int, default=20)
    parser.add_argument("--delay", type=float, default=3.0)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--expected-industry", default="art")
    parser.add_argument("--download-images", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.max_pages < 1 or args.max_contests < 1:
        raise CollectionError("--max-pages and --max-contests must be positive")
    authorization = read_authorization(args.authorization_file)
    user_agent = f"CurifyDesignResearch/0.1 (contact: {args.contact_email})"
    client = PoliteClient(
        user_agent=user_agent,
        delay_seconds=args.delay,
        timeout_seconds=args.timeout,
        max_retries=args.max_retries,
    )

    robots_result = client.get(ROBOTS_URL, max_bytes=2 * 1024 * 1024, accept="text/plain")
    robots_policy = RobotsPolicy.parse(robots_result.text())
    robots_allowed = robots_policy.can_fetch(user_agent, args.list_url)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "list_url": args.list_url,
                    "robots_allowed": robots_allowed,
                    "authorization_fingerprint": authorization.fingerprint,
                    "would_download_images": args.download_images,
                },
                indent=2,
            )
        )
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    records_path = args.output_dir / "contests.jsonl"
    failures_path = args.output_dir / "failures.jsonl"
    urls_path = args.output_dir / "discovered-urls.txt"
    done = completed_urls(records_path)

    urls = discover_urls(client, args.list_url, args.max_pages)
    urls_path.write_text("\n".join(urls) + ("\n" if urls else ""), encoding="utf-8")
    attempted = 0
    collected = 0
    skipped = 0
    failed = 0
    for source_url in urls:
        if collected >= args.max_contests:
            break
        if source_url in done:
            skipped += 1
            continue
        attempted += 1
        try:
            result = client.get(
                source_url,
                max_bytes=MAX_HTML_BYTES,
                accept="text/html,application/xhtml+xml",
            )
            record = extract_contest(result.text(), result.url, authorization)
            industry = (record.get("industry") or {}).get("key")
            if args.expected_industry and industry != args.expected_industry:
                raise CollectionError(
                    f"industry mismatch: expected {args.expected_industry!r}, got {industry!r}"
                )
            if args.download_images:
                download_winners(client, record, args.output_dir)
            append_jsonl(records_path, record)
            done.add(source_url)
            collected += 1
            print(f"collected {record['contest_id']}: {record['title']}", flush=True)
        except (CollectionError, OSError, ValueError) as exc:
            failed += 1
            append_jsonl(
                failures_path,
                {
                    "source_url": source_url,
                    "failed_at": utc_now(),
                    "error": str(exc),
                },
            )
            print(f"failed {source_url}: {exc}", file=sys.stderr, flush=True)

    summary = {
        "schema_version": "99designs-collection-run-v0.1",
        "finished_at": utc_now(),
        "list_url": args.list_url,
        "robots_allowed": robots_allowed,
        "authorization_fingerprint": authorization.fingerprint,
        "download_images": args.download_images,
        "discovered": len(urls),
        "attempted": attempted,
        "collected": collected,
        "skipped_existing": skipped,
        "failed": failed,
    }
    write_run_summary(args.output_dir, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if collected else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CollectionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
