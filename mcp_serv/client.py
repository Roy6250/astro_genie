"""
MCP SSE client: call_tool(name, arguments) to invoke tools on the MCP server.
Use MCP_SERVER_URL (e.g. http://localhost:8001/sse) from config/env.
"""
import asyncio
import logging
from typing import Any

from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
import logging

logger = logging.getLogger(__name__)

# Default timeout for tool call (seconds)
DEFAULT_TIMEOUT = 30.0


async def call_tool(
    url: str,
    name: str,
    arguments: dict[str, Any],
    timeout: float = DEFAULT_TIMEOUT,
) -> str | dict[str, Any]:
    """
    Connect to MCP server via SSE and call a tool.
    :param url: SSE endpoint URL (e.g. http://localhost:8001/sse).
    :param name: Tool name (e.g. get_daily_horoscope).
    :param arguments: Tool arguments dict (e.g. {"sign": "virgo"}).
    :param timeout: HTTP/SSE timeout in seconds.
    :return: Tool result as string (text content) or dict; user-friendly error string on failure.
    """
    try:
        logger.info("MCP call start url=%s tool=%s args_keys=%s", url, name, sorted(list(arguments.keys())))
        async with sse_client(url, timeout=timeout, sse_read_timeout=timeout) as (read_stream, write_stream):
            async with ClientSession(read_stream=read_stream, write_stream=write_stream) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
                if getattr(result, "isError", False):
                    parts = []
                    for c in (result.content or []):
                        if getattr(c, "text", None):
                            parts.append(c.text)
                    msg = " ".join(parts) or "Tool returned an error."
                    logger.warning("MCP call error tool=%s chars=%d", name, len(msg))
                    return msg
                parts = []
                for c in (result.content or []):
                    if getattr(c, "text", None):
                        parts.append(c.text)
                output = "\n".join(parts).strip() if parts else ""
                logger.info("MCP call success tool=%s chars=%d", name, len(output))
                return output
    except asyncio.TimeoutError:
        logger.warning("MCP call_tool timeout: %s", url)
        return "The horoscope service is taking too long. Please try again in a moment."
    except ConnectionError as e:
        logger.warning("MCP connection error: %s", e)
        return "The horoscope service is unavailable right now. Please try again later."
    except Exception as e:
        logger.exception("MCP call_tool failed: %s", e)
        return "Something went wrong fetching your horoscope. Please try again later."
