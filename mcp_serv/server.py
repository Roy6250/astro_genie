"""
MCP server with SSE transport. Exposes tool get_daily_horoscope(sign, date).
Run from astro_genie directory: python -m mcp_serv.server
"""
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

from mcp import types
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route

from integrations.prokerala.daily_horoscope import get_daily_horoscope
from integrations.prokerala.formatter import format_daily_horoscope_response

app = Server("astro-genie-mcp")


@app.list_tools()
async def handle_list_tools(
    _request: types.ListToolsRequest | None = None,
) -> types.ListToolsResult:
    return types.ListToolsResult(
        tools=[
            types.Tool(
                name="get_daily_horoscope",
                description="Get daily horoscope (General, Career, Love, Health) for a zodiac sign.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sign": {
                            "type": "string",
                            "description": "Zodiac sign (lowercase): aries, taurus, gemini, cancer, leo, virgo, libra, scorpio, sagittarius, capricorn, aquarius, pisces",
                        },
                        "date": {
                            "type": "string",
                            "description": "Optional date in YYYY-MM-DD; default is today.",
                        },
                    },
                    # "required": ["sign"],
                },
            )
        ]
    )


@app.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    if name != "get_daily_horoscope":
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]
    args = arguments or {}
    logger.info("Calling get_daily_horoscope with args: %s", args)
    sign = (args.get("sign") or "").strip().lower()
    if not sign:
        return [types.TextContent(type="text", text="Missing required argument: sign")]
    dt = None
    if args.get("date"):
        try:
            dt = datetime.strptime(str(args["date"]).strip()[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    raw = get_daily_horoscope(sign, dt)
    formatted = format_daily_horoscope_response(raw)
    return [types.TextContent(type="text", text=formatted)]


def create_starlette_app():
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request):
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await app.run(streams[0], streams[1], app.create_initialization_options())
        return Response()

    return Starlette(
        debug=os.getenv("MCP_DEBUG", "").lower() in ("1", "true"),
        routes=[
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )


# For uvicorn: app is the Starlette ASGI app
app_asgi = create_starlette_app()


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "8001"))
    uvicorn.run(app_asgi, host=host, port=port)
