"""rss-digest-mcp — a zero-dependency RSS *competitive-intelligence* MCP server.

Point it at a list of public RSS/Atom feeds (competitor blogs, industry news,
job boards, release notes) and ask for a keyword-filtered, de-duplicated,
recency-sorted digest. No database, no API keys, no login — just feed parsing.

Tools
-----
- ``get_digest(feeds, keywords, hours, max_items)`` — the headline tool: one
  combined, deduped, filtered digest across many feeds.
- ``fetch_feed(url, limit)``                       — latest items of one feed.
- ``load_opml(path)``                              — bulk-load feed URLs from a
  local OPML export (the usual way power-users keep their feed list).

Privacy: the server is stateless. It does not persist feed contents or any
user data; everything is fetched on demand and returned, then forgotten.
"""

from __future__ import annotations

import socket
from typing import Optional

import feedparser
from mcp.server.fastmcp import FastMCP

from .core import Item, digest, to_item, truncate_summary

# A feed that hangs should never hang the whole tool call.
_DEFAULT_TIMEOUT = 10
socket.setdefaulttimeout(_DEFAULT_TIMEOUT)

mcp = FastMCP("rss-digest")


def _fetch_one(url: str) -> tuple[list[Item], str, Optional[str]]:
    """Fetch + parse one feed. Returns (items, feed_title, error_or_None).

    feedparser handles RSS, Atom and JSON feeds and decodes legacy Japanese
    encodings (Shift_JIS / EUC-JP) transparently, so NHK / Zenn / Qiita work
    out of the box.
    """
    parsed = feedparser.parse(url)
    feed_title = (parsed.feed.get("title") if parsed.feed else None) or url
    # feedparser sets ``bozo`` on malformed feeds but still returns entries;
    # only treat it as an error when nothing at all came back.
    if not parsed.entries and parsed.get("bozo"):
        exc = parsed.get("bozo_exception")
        return [], feed_title, f"parse error: {exc}"[:200]
    items = [to_item(e, feed_title) for e in parsed.entries]
    return items, feed_title, None


@mcp.tool()
def get_digest(
    feeds: list[str],
    keywords: Optional[list[str]] = None,
    hours: int = 24,
    max_items: int = 30,
    summary_max_chars: int = 0,
) -> dict:
    """Build one competitive-intelligence digest across many RSS/Atom feeds.

    Args:
        feeds: RSS/Atom feed URLs to pull from (competitor blogs, news, jobs…).
        keywords: only keep items whose title/summary contains one of these
            (case-insensitive). Omit or pass [] to get everything recent.
        hours: only keep items published within the last N hours (default 24).
            Undated items are kept. Pass 0 to disable the time filter.
        max_items: cap on returned items after dedup + sort (default 30).
        summary_max_chars: optionally shorten each item's summary to this many
            characters (with an ellipsis) to keep the digest compact. Default 0
            = no truncation (full summaries).

    Returns a dict with the matched ``items`` (newest first, deduped by link),
    a ``count``, how many feeds succeeded, and any per-feed ``errors``.
    """
    all_items: list[Item] = []
    errors: list[dict] = []
    for url in feeds:
        try:
            items, _title, err = _fetch_one(url)
            if err:
                errors.append({"feed": url, "error": err})
            all_items.extend(items)
        except Exception as exc:  # network/DNS/etc — never abort the whole call
            errors.append({"feed": url, "error": str(exc)[:200]})

    result = digest(all_items, keywords or [], hours, max_items)
    if summary_max_chars and summary_max_chars > 0:
        for it in result:
            it.summary = truncate_summary(it.summary, summary_max_chars)
    return {
        "count": len(result),
        "feeds_requested": len(feeds),
        "feeds_ok": len(feeds) - len(errors),
        "errors": errors,
        "items": [i.as_dict() for i in result],
    }


@mcp.tool()
def fetch_feed(url: str, limit: int = 20, summary_max_chars: int = 0) -> dict:
    """Fetch a single RSS/Atom feed and return its latest items (newest first).

    ``summary_max_chars`` optionally shortens each summary (default 0 = full).
    """
    items, feed_title, err = _fetch_one(url)
    items.sort(key=lambda i: (i.published_ts or 0.0), reverse=True)
    capped = items[: limit if limit and limit > 0 else len(items)]
    if summary_max_chars and summary_max_chars > 0:
        for it in capped:
            it.summary = truncate_summary(it.summary, summary_max_chars)
    return {
        "feed_title": feed_title,
        "feed_url": url,
        "error": err,
        "count": len(capped),
        "items": [i.as_dict() for i in capped],
    }


@mcp.tool()
def load_opml(path: str) -> dict:
    """Read a local OPML file and return the feed list (title + xmlUrl).

    Use this to bulk-onboard a feed collection exported from another reader,
    then pass the URLs to ``get_digest``. Only reads the file you point at.
    """
    import xml.etree.ElementTree as ET

    tree = ET.parse(path)
    feeds: list[dict] = []
    for outline in tree.iter("outline"):
        xml_url = outline.get("xmlUrl")
        if xml_url:
            feeds.append(
                {
                    "title": outline.get("title") or outline.get("text") or "",
                    "xmlUrl": xml_url,
                }
            )
    return {"count": len(feeds), "feeds": feeds}


def main() -> None:
    """Console-script / ``python -m`` entry point. Speaks MCP over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
