"""Allow ``python -m rss_digest_mcp`` to start the MCP server.

This is the most portable launch path (no console-script PATH lookup, no uv):
after ``pip install -e .`` (or with the deps installed and ``src`` on the
path), ``python -m rss_digest_mcp`` speaks MCP over stdio.
"""

from .server import main

if __name__ == "__main__":
    main()
