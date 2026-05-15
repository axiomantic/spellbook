"""Canvas: agent-authored markdown pages rendered in the admin UI.

A canvas is a named directory under ``~/.local/spellbook/canvas/<name>/``
containing a single markdown page (``pages/index.md``), an empty inbox
reserved for v2, and a ``meta.json`` metadata file. Canvases are agent
writable through the MCP tool layer (``spellbook.mcp.tools.canvas``) and
read-only through the admin HTTP layer (``spellbook.admin.routes.canvas``).

Threat model: canvas content is TRUSTED-LOCAL-AGENT output only. Agents
MUST NOT write unsanitized external content (chat transcripts, fetched
web pages, untrusted MCP tool outputs, user-pasted strings) into a canvas
— ``rehype-raw`` lets raw HTML execute under the admin's auth context, so
a script tag is a session-takeover primitive.
"""
