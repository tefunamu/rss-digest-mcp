"""Pure, dependency-free digest logic.

This module deliberately imports only the standard library so the core
behaviour (recency filter, keyword match, dedup, sort) is unit-testable
without installing the MCP SDK or feedparser. The network/MCP layer lives
in ``server.py`` and reuses everything here.

Design principle: this server is **stateless** — it never stores feed
contents or any personal data. Items flow in, get filtered, and are
returned. Nothing is persisted.
"""

from __future__ import annotations

import calendar
import re
import time
from dataclasses import dataclass, asdict
from typing import Any, Iterable, Optional

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


@dataclass
class Item:
    """One feed entry, normalised across RSS / Atom / JSON feeds."""

    title: str
    link: str
    summary: str
    source: str                      # the feed's own title
    published: Optional[str] = None  # ISO-8601 UTC, e.g. 2026-06-25T01:00:00Z
    published_ts: Optional[float] = None  # epoch seconds (UTC), for sorting

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def clean_text(html: str) -> str:
    """Strip HTML tags and collapse whitespace — no external deps."""
    if not html:
        return ""
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", html)).strip()


def truncate_summary(text: str, max_chars: int) -> str:
    """Shorten ``text`` to ``max_chars`` and append an ellipsis.

    Opt-in: ``max_chars <= 0`` (the default everywhere) returns the text
    unchanged. Trailing whitespace before the cut is trimmed so the ellipsis
    sits flush against the last word.
    """
    if not max_chars or max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"


def entry_timestamp(entry: Any) -> Optional[float]:
    """Best-effort UTC epoch seconds from a feedparser-style entry.

    feedparser exposes ``*_parsed`` fields as ``time.struct_time`` in UTC,
    so ``calendar.timegm`` is the correct (timezone-safe) converter.
    """
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            try:
                return float(calendar.timegm(t))
            except (TypeError, ValueError):
                continue
    return None


def to_item(entry: Any, source_title: str) -> Item:
    """Convert a feedparser-style entry (anything with ``.get``) into an Item."""
    ts = entry_timestamp(entry)
    published = (
        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)) if ts is not None else None
    )
    return Item(
        title=(entry.get("title") or "").strip(),
        link=(entry.get("link") or "").strip(),
        summary=clean_text(entry.get("summary") or entry.get("description") or ""),
        source=source_title,
        published=published,
        published_ts=ts,
    )


def matches_keywords(item: Item, keywords: Iterable[str]) -> bool:
    """Case-insensitive substring match over title + summary.

    Empty keyword list => everything matches (pure recency digest).
    """
    kws = [k.lower() for k in keywords if k]
    if not kws:
        return True
    hay = f"{item.title} {item.summary}".lower()
    return any(k in hay for k in kws)


def within_hours(item: Item, hours: Optional[int], *, now: Optional[float] = None) -> bool:
    """Keep items newer than ``hours``. Undated items are kept (over-include
    is safer for intelligence than silently dropping)."""
    if not hours or hours <= 0:
        return True
    if item.published_ts is None:
        return True
    now = time.time() if now is None else now
    return item.published_ts >= now - hours * 3600


def digest(
    items: Iterable[Item],
    keywords: Iterable[str] = (),
    hours: Optional[int] = 24,
    max_items: int = 30,
    *,
    now: Optional[float] = None,
) -> list[Item]:
    """Filter by recency + keywords, dedup by link, sort newest-first, cap.

    Dedup key is the item link; items without a link fall back to
    ``source|title`` so two different feeds can't collide.
    """
    seen: set[str] = set()
    out: list[Item] = []
    for it in items:
        if not within_hours(it, hours, now=now):
            continue
        if not matches_keywords(it, keywords):
            continue
        key = it.link or f"{it.source}|{it.title}"
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    out.sort(key=lambda i: (i.published_ts or 0.0), reverse=True)
    return out[: max_items if max_items and max_items > 0 else len(out)]
