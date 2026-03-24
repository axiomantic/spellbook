"""MCP tools for tooling discovery."""

__all__ = ["tooling_discover"]

from fastmcp import Context

from spellbook.core.path_utils import get_project_path_from_context
from spellbook.mcp.server import mcp
from spellbook.sessions.injection import inject_recovery_context


@mcp.tool()
@inject_recovery_context
async def tooling_discover(
    ctx: Context,
    domain_keywords: str,
    project_path: str = "",
) -> dict:
    """Discover available tools for a technology domain.

    Searches the tooling registry, active MCP tools, project dependencies,
    and local CLI availability to find relevant tools for the given domain.

    Args:
        domain_keywords: Comma-separated keywords describing the domain
            (e.g., "jira,project-management" or "docker,kubernetes").
        project_path: Optional project root path for dependency scanning.
            Auto-detected if empty.

    Returns:
        Dict with discovered tools grouped by trust tier.
    """
    from spellbook.tooling.discovery import discover_tools

    keywords = [kw.strip() for kw in domain_keywords.split(",") if kw.strip()]
    if not keywords:
        return {"error": "No keywords provided. Pass comma-separated domain keywords."}

    if not project_path:
        detected = await get_project_path_from_context(ctx)
        if detected:
            project_path = detected

    return discover_tools(
        domain_keywords=keywords,
        project_path=project_path,
    )
