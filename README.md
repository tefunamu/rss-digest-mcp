# rss-digest-mcp

A stateless **RSS competitive-intelligence** MCP server. Point it at a list of
public RSS/Atom feeds — competitor blogs, industry news, release notes, job
boards — and get back a **keyword-filtered, de-duplicated, recency-sorted
digest**. No database, no API keys, no login.

> "What did my three competitors and the two industry news sites publish in the
> last 24 hours that mention *pricing* or *layoffs*?" — one tool call.

## What it does

`rss-digest-mcp` turns a pile of feed URLs into a single, focused digest. It
fetches and parses each feed, keeps only items that (a) are recent enough and
(b) match your keywords, removes duplicates across feeds, sorts newest-first,
and returns clean structured items your LLM can summarise or act on.

It is **stateless and privacy-respecting**: nothing is stored. Feeds are fetched
on demand, filtered, returned, and forgotten. No personal data is collected.

## Why MCP

Reading feeds is easy; *deciding what matters* is the work. By exposing this as
an MCP server, the filtering/dedup/recency logic runs deterministically in the
tool, and the LLM (Claude, Cursor, Cline…) does what it is good at on top:
summarising the digest, spotting themes, drafting an alert. The model never has
to fetch or page through raw XML, and the same server works identically across
every MCP client — so a "morning competitive brief" is one natural-language
request away.

## Quick Start

> **This is a tool server, not a CLI reader.** It does not print feeds on its
> own. It exposes tools that an **MCP client (Claude Code, Claude Desktop,
> Cursor, Cline) calls for you**. You get RSS digests by connecting it to a
> client and *asking in plain language* — not by running a command here.

So the only required step is **[Configuration](#configuration)** (connect it to
your client). The steps below are an **optional** sanity check.

Requires Python ≥ 3.10; the client launches the server via
[`uv`](https://docs.astral.sh/uv/).

```bash
# (optional) clone + run the tests — stdlib only, no install, proves it works
git clone https://github.com/tefunamu/rss-digest-mcp.git
cd rss-digest-mcp
python3 -m unittest discover -s tests -v        # 16 tests, expect "OK"
```

You do **not** need to start the server by hand — your MCP client does that.
If you just want to confirm it boots, `uvx --from . rss-digest-mcp` will sit
silently waiting for a client to speak MCP over stdio (that silence is correct —
there is no output until a client calls a tool). Press Ctrl-C to stop.

Once connected (next section), ask your client something like:

> *"Use get_digest on `https://hnrss.org/frontpage` and `https://zenn.dev/feed`,
> keywords AI, last 24 hours."*

## Configuration

The server speaks MCP over **stdio**. Add one of the blocks below to your
client, then ask: *"Use get_digest on these feeds for the last 24h with
keywords pricing, funding."*

> Use the **absolute** path to this repo in every example below. A wrong/relative
> path is the #1 reason the server silently fails to start.
>
> **Windows ARM64 users:** install the package with the constraints file first —
> see [Troubleshooting › Windows ARM64](#windows-arm64-cryptography-fails-to-build-linkexe-not-found).

### Claude Code
```bash
# from anywhere — register the server (use the absolute repo path)
claude mcp add rss-digest -- uvx --from /ABSOLUTE/PATH/TO/rss-digest-mcp rss-digest-mcp
# add -s user to make it available in every project:
#   claude mcp add -s user rss-digest -- uvx --from /ABSOLUTE/PATH/TO/rss-digest-mcp rss-digest-mcp

claude mcp list            # should show  rss-digest: ✓ connected
```
Then in a new session: *"Use get_digest on https://zenn.dev/feed, keywords AI, last 24h."*

### Claude Desktop
`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) /
`%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "rss-digest": {
      "command": "uvx",
      "args": ["--from", "/ABSOLUTE/PATH/TO/rss-digest-mcp", "rss-digest-mcp"]
    }
  }
}
```

### Cursor
`~/.cursor/mcp.json` (or **Settings → MCP → Add**):

```json
{
  "mcpServers": {
    "rss-digest": {
      "command": "uvx",
      "args": ["--from", "/ABSOLUTE/PATH/TO/rss-digest-mcp", "rss-digest-mcp"]
    }
  }
}
```

### Cline (VS Code)
`cline_mcp_settings.json` (**Cline → MCP Servers → Configure**):

```json
{
  "mcpServers": {
    "rss-digest": {
      "command": "uvx",
      "args": ["--from", "/ABSOLUTE/PATH/TO/rss-digest-mcp", "rss-digest-mcp"],
      "disabled": false
    }
  }
}
```

## Tools provided

> **What these tools are *not*:** `get_digest` is a *deterministic filter* over
> the feeds **you give it** — it matches keywords as plain substrings and sorts
> by recency. It does **not** search the web, and it does **not** infer which
> feeds a topic belongs to. Choosing the right feed URLs, turning a question into
> keywords, and judging whether a hit is actually relevant is the **client's
> (the LLM's) job** — the tool just fetches, filters and dedups. So "find what
> Japanese electronics makers said about pricing" only works if the client first
> supplies those makers' feed URLs and sensible keywords.

| Tool | Arguments | Returns |
|------|-----------|---------|
| `get_digest` | `feeds: string[]`, `keywords?: string[]`, `hours: int = 24`, `max_items: int = 30`, `summary_max_chars: int = 0` | Combined digest across all feeds: matched items (newest first, deduped by link), `count`, `feeds_ok`, per-feed `errors`. Empty `keywords` = pure recency digest; `hours = 0` disables the time filter; `summary_max_chars > 0` shortens each summary (default `0` = full). |
| `fetch_feed` | `url: string`, `limit: int = 20`, `summary_max_chars: int = 0` | Latest items of one feed (newest first), plus `feed_title` and any parse `error`. `summary_max_chars > 0` shortens summaries. |
| `load_opml` | `path: string` | Feed list (`title` + `xmlUrl`) parsed from a local OPML export, for bulk onboarding. Reads only the file you point at. |

Each returned item has: `title`, `link`, `summary` (HTML-stripped),
`source` (feed title), `published` (ISO-8601 UTC), `published_ts` (epoch).

### Example feeds (incl. Japanese sources)

Works with any RSS/Atom feed. `feedparser` decodes legacy Japanese encodings
(Shift_JIS / EUC-JP) transparently, so Japanese sources work out of the box:

- Hacker News front page — `https://hnrss.org/frontpage`
- NHK 主要ニュース — `https://www.nhk.or.jp/rss/news/cat0.xml`
- Zenn (trending) — `https://zenn.dev/feed`
- Qiita (popular) — `https://qiita.com/popular-items/feed`
- GitHub repo releases — `https://github.com/<owner>/<repo>/releases.atom`

## Usage examples

Once connected, you drive it in **plain language** — your MCP client turns the
request into the right tool call. Examples (paste into Claude / Cursor / Cline):

**Competitive / industry monitoring**
> Use `get_digest` on `https://hnrss.org/frontpage` and `https://techcrunch.com/feed/`,
> keywords `pricing, layoffs, funding`, last 24 hours, then summarize the themes.

**Japanese tech news, compact summaries**
> `get_digest` on `https://zenn.dev/feed` and `https://qiita.com/popular-items/feed`,
> keyword `AI`, last 24h, `summary_max_chars` 200.

**Just the latest from one source**
> `fetch_feed` `https://news.ycombinator.com/rss`, limit 10.

**Onboard a feed list, then digest it**
> `load_opml` `./feeds.opml`, then `get_digest` on those URLs with keyword `AI`.

A real run — 2 feeds, keyword `AI`, last 24h, `summary_max_chars=200` — returns:

```json
{
  "count": 5,
  "feeds_requested": 2,
  "feeds_ok": 2,
  "errors": [],
  "items": [
    {
      "title": "OpenAI unveils its first custom chip, built by Broadcom",
      "link": "https://techcrunch.com/2026/06/24/openai-unveils-its-first-custom-chip-built-by-broadcom/",
      "summary": "Announcement: …",
      "source": "Hacker News: Front Page",
      "published": "2026-06-24T17:47:00Z",
      "published_ts": 1782323220.0
    }
    // … 4 more, newest first, deduped across both feeds
  ]
}
```

The client (the LLM) chooses the feeds + keywords and reads this back to you as a
brief; the tool just fetches, filters and dedups.

## Architecture

```
MCP client (Claude Desktop / Cursor / Cline)
        │  stdio (MCP)
        ▼
server.py  ── FastMCP tools: get_digest / fetch_feed / load_opml
        │        │
        │        └─ feedparser  →  fetch + parse RSS/Atom/JSON (handles JP encodings)
        ▼
core.py    ── pure, stdlib-only logic: recency filter · keyword match ·
              dedup-by-link · newest-first sort · cap
```

The split is deliberate: **`core.py` has zero third-party imports**, so the
business logic is fully unit-tested without the network or the MCP SDK
(`server.py` is the thin I/O shell). Stateless by design — no storage layer.

## Testing

```bash
python3 -m unittest discover -s tests -v
```

The suite covers HTML cleaning, UTC timestamp handling, keyword matching,
the recency window (including undated items), and the dedup/sort/cap pipeline —
all with a fixed clock for determinism.

## Troubleshooting

### MCP client shows "Failed to connect"
The launch command isn't runnable. Either install `uv` (`pip install uv`) so
`uvx` works, or use the no-uv path: `pip install -e .` then register the server
as `python -m rss_digest_mcp`. After changing the client config, start a **new**
session — existing sessions don't pick up new servers.

### Windows ARM64: `cryptography` fails to build / `uvx` won't connect
On native win-arm64, `cryptography` ≥ 47 ships **no prebuilt wheel**, so pip
falls back to a Rust source build that needs MSVC `link.exe` and fails on a clean
machine (`cryptography` arrives transitively via the MCP SDK → `pyjwt[crypto]`).
The `uvx --from .` launch in [Configuration](#configuration) **also fails here**,
because uvx builds the package in a fresh isolated env and *ignores the
constraints file*, re-triggering that same source build.

Use the **pip + `python -m`** path instead:

```bash
# 1. install, pinned to cryptography's last win-arm64 wheel (46.0.3)
python -m pip install -e . -c constraints-winarm64.txt --only-binary=cryptography

# 2. register with the module launcher (NOT uvx)
claude mcp add -s user rss-digest -- python -m rss_digest_mcp
claude mcp list      # rss-digest ... ✓ connected
```

Notes:
- The pin is **environment-specific** — x64 / macOS / Linux have current wheels —
  so it lives in [`constraints-winarm64.txt`](constraints-winarm64.txt), **not**
  in `pyproject.toml` (which would needlessly hold those platforms back).
- `claude mcp add` records the **absolute path** of the `python` you used. If you
  later move or replace that interpreter, re-run `claude mcp add`.
- If you must keep using `uvx`, pass the constraints via the `UV_CONSTRAINT`
  environment variable — but that still rebuilds the isolated env, so the direct
  `python -m` launch is lighter and more reliable.

## License

MIT — see [LICENSE](LICENSE).
