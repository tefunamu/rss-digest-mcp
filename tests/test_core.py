"""Unit tests for the pure digest logic (stdlib only — no network, no SDK).

Run with:  python3 -m unittest discover -s tests -v
"""

import calendar
import os
import sys
import time
import unittest

# Make the src-layout package importable when running the tests directly
# (`python -m unittest discover -s tests`) without installing or setting
# PYTHONPATH. The core logic is dependency-free, so tests run with stdlib only.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from rss_digest_mcp.core import (
    Item,
    clean_text,
    digest,
    entry_timestamp,
    matches_keywords,
    to_item,
    truncate_summary,
    within_hours,
)

# A fixed "now" so recency tests are deterministic: 2026-06-25T00:00:00Z.
NOW = float(calendar.timegm((2026, 6, 25, 0, 0, 0, 0, 0, 0)))


def _struct(hours_ago: float):
    return time.gmtime(NOW - hours_ago * 3600)


def _item(title="", summary="", link="", source="src", hours_ago=1.0):
    ts = NOW - hours_ago * 3600
    return Item(
        title=title,
        link=link,
        summary=summary,
        source=source,
        published=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)),
        published_ts=ts,
    )


class CleanTextTests(unittest.TestCase):
    def test_strips_tags_and_whitespace(self):
        self.assertEqual(clean_text("<p>Hello   <b>world</b></p>"), "Hello world")

    def test_empty(self):
        self.assertEqual(clean_text(""), "")


class TruncateSummaryTests(unittest.TestCase):
    def test_zero_or_negative_is_noop(self):
        self.assertEqual(truncate_summary("hello world", 0), "hello world")
        self.assertEqual(truncate_summary("hello world", -5), "hello world")

    def test_shorter_than_limit_unchanged(self):
        self.assertEqual(truncate_summary("short", 100), "short")

    def test_truncates_with_ellipsis_and_trims(self):
        # 10-char cut of "the quick brown" -> "the quick " -> rstrip -> "the quick…"
        self.assertEqual(truncate_summary("the quick brown fox", 10), "the quick…")


class TimestampTests(unittest.TestCase):
    def test_published_parsed_is_utc(self):
        entry = {"published_parsed": _struct(0)}
        self.assertEqual(entry_timestamp(entry), NOW)

    def test_falls_back_to_updated(self):
        entry = {"updated_parsed": _struct(2)}
        self.assertAlmostEqual(entry_timestamp(entry), NOW - 7200)

    def test_missing_dates_returns_none(self):
        self.assertIsNone(entry_timestamp({"title": "x"}))


class ToItemTests(unittest.TestCase):
    def test_maps_fields_and_cleans_summary(self):
        entry = {
            "title": " Big news ",
            "link": "https://ex.com/a",
            "summary": "<p>body</p>",
            "published_parsed": _struct(1),
        }
        it = to_item(entry, "ACME Blog")
        self.assertEqual(it.title, "Big news")
        self.assertEqual(it.link, "https://ex.com/a")
        self.assertEqual(it.summary, "body")
        self.assertEqual(it.source, "ACME Blog")
        self.assertTrue(it.published.endswith("Z"))


class KeywordTests(unittest.TestCase):
    def test_empty_keywords_match_all(self):
        self.assertTrue(matches_keywords(_item(title="anything"), []))

    def test_case_insensitive_substring(self):
        it = _item(title="New GPT release", summary="details")
        self.assertTrue(matches_keywords(it, ["gpt"]))
        self.assertFalse(matches_keywords(it, ["llama"]))

    def test_matches_in_summary(self):
        it = _item(title="t", summary="quarterly pricing change")
        self.assertTrue(matches_keywords(it, ["PRICING"]))


class RecencyTests(unittest.TestCase):
    def test_within_window(self):
        self.assertTrue(within_hours(_item(hours_ago=5), 24, now=NOW))

    def test_outside_window(self):
        self.assertFalse(within_hours(_item(hours_ago=50), 24, now=NOW))

    def test_undated_kept(self):
        it = Item(title="t", link="l", summary="s", source="x", published_ts=None)
        self.assertTrue(within_hours(it, 24, now=NOW))

    def test_zero_disables_filter(self):
        self.assertTrue(within_hours(_item(hours_ago=9999), 0, now=NOW))


class DigestTests(unittest.TestCase):
    def test_filters_dedups_sorts_and_caps(self):
        items = [
            _item(title="GPT pricing drop", link="https://a", hours_ago=2),
            _item(title="GPT pricing drop", link="https://a", hours_ago=2),  # dup link
            _item(title="GPT new model", link="https://b", hours_ago=1),
            _item(title="unrelated cat video", link="https://c", hours_ago=1),
            _item(title="GPT old news", link="https://d", hours_ago=100),  # too old
        ]
        out = digest(items, keywords=["gpt"], hours=24, max_items=10, now=NOW)
        links = [i.link for i in out]
        self.assertEqual(links, ["https://b", "https://a"])  # newest first, deduped

    def test_max_items_cap(self):
        items = [_item(title="gpt", link=f"https://{n}", hours_ago=n) for n in range(1, 6)]
        out = digest(items, keywords=["gpt"], hours=0, max_items=3, now=NOW)
        self.assertEqual(len(out), 3)

    def test_no_keywords_returns_all_recent(self):
        items = [_item(title=f"item {n}", link=f"https://{n}", hours_ago=1) for n in range(3)]
        out = digest(items, keywords=[], hours=24, max_items=10, now=NOW)
        self.assertEqual(len(out), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
