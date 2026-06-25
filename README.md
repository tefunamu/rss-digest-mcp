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

Requires Python ≥ 3.10. The fastest path uses [`uv`](https://docs.astral.sh/uv/)
(no manual venv, no global installs):

```bash
# 1. clone
git clone https://github.com/tefunamu/rss-digest-mcp.git
cd rss-digest-mcp

# 2. run the tests (stdlib only — proves the core logic works)
python3 -m unittest discover -s tests -v

# 3. run the server (stdio) — usually your MCP client launches this for you
uvx --from . rss-digest-mcp
```

That's it. There is no config file, no database to provision, and no key to
paste.

## Configuration

The server speaks MCP over **stdio**. Add one of the blocks below to your
client, then ask: *"Use get_digest on these feeds for the last 24h with
keywords pricing, funding."*

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

| Tool | Arguments | Returns |
|------|-----------|---------|
| `get_digest` | `feeds: string[]`, `keywords?: string[]`, `hours: int = 24`, `max_items: int = 30` | Combined digest across all feeds: matched items (newest first, deduped by link), `count`, `feeds_ok`, per-feed `errors`. Empty `keywords` = pure recency digest; `hours = 0` disables the time filter. |
| `fetch_feed` | `url: string`, `limit: int = 20` | Latest items of one feed (newest first), plus `feed_title` and any parse `error`. |
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

## License

MIT — see [LICENSE](LICENSE).
