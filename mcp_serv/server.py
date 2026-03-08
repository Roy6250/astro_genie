"""
MCP server with SSE transport.
Exposes tools:
- get_daily_horoscope(sign, date)
- get_kundli(date_of_birth, time_of_birth, place, ...)
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
from integrations.prokerala.formatter import format_daily_horoscope_response_with_context
from integrations.prokerala.kundli import (
    get_kundli,
    format_kundli_response,
    get_dasha_details,
    format_dasha_response,
    get_mangal_dosha_details,
    format_mangal_dosha_response,
)

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
                        "user_name": {
                            "type": "string",
                            "description": "Optional user name for personalized greeting.",
                        },
                        "persona_context": {
                            "type": "object",
                            "description": "Optional user persona context (numerology/astrology) for personal touch.",
                        },
                    },
                    # "required": ["sign"],
                },
            ),
            types.Tool(
                name="get_kundli",
                description="Generate detailed kundli with dasha periods and mangal dosha details.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "date_of_birth": {
                            "type": "string",
                            "description": "Birth date in YYYY-MM-DD format.",
                        },
                        "time_of_birth": {
                            "type": "string",
                            "description": "Birth time in HH:MM (24h). Default 12:00.",
                        },
                        "place": {
                            "type": "string",
                            "description": "Place of birth (city, state/country). Used for free geocoding.",
                        },
                        "latitude": {
                            "type": "number",
                            "description": "Optional latitude override.",
                        },
                        "longitude": {
                            "type": "number",
                            "description": "Optional longitude override.",
                        },
                        "timezone": {
                            "type": "string",
                            "description": "Optional IANA timezone override (e.g. Asia/Kolkata).",
                        },
                        "ayanamsa": {
                            "type": "string",
                            "description": "Optional ayanamsa code/name. Allowed: 1|3|5 or lahiri|raman|kp. Defaults to 1 (Lahiri).",
                        },
                        "la": {
                            "type": "string",
                            "description": "Language code. Allowed: en, hi, ta, ml.",
                        },
                        "language": {
                            "type": "string",
                            "description": "Alias of 'la' for backward compatibility.",
                        },
                        "year_length": {
                            "type": "number",
                            "description": "For dasha periods. 1 => 365.25 days/year, 0 => 360 days/year. Default 1.",
                        },
                        "include_dasha_periods": {
                            "type": "boolean",
                            "description": "Include dasha periods in response. Default true.",
                        },
                        "include_mangal_dosha": {
                            "type": "boolean",
                            "description": "Include mangal dosha details in response. Default true.",
                        },
                    },
                    "required": ["date_of_birth", "place"],
                },
            ),
            types.Tool(
                name="get_dasha_details",
                description="Get focused dasha details for the birth profile.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "date_of_birth": {"type": "string"},
                        "time_of_birth": {"type": "string"},
                        "place": {"type": "string"},
                        "latitude": {"type": "number"},
                        "longitude": {"type": "number"},
                        "timezone": {"type": "string"},
                        "ayanamsa": {"type": "string"},
                        "la": {"type": "string"},
                        "year_length": {"type": "number"},
                    },
                    "required": ["date_of_birth", "place"],
                },
            ),
            types.Tool(
                name="get_mangal_dosha_details",
                description="Get focused mangal dosha details for the birth profile.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "date_of_birth": {"type": "string"},
                        "time_of_birth": {"type": "string"},
                        "place": {"type": "string"},
                        "latitude": {"type": "number"},
                        "longitude": {"type": "number"},
                        "timezone": {"type": "string"},
                        "ayanamsa": {"type": "string"},
                        "la": {"type": "string"},
                    },
                    "required": ["date_of_birth", "place"],
                },
            ),
        ]
    )


@app.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    args = arguments or {}
    if name == "get_daily_horoscope":
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
        user_name = str(args.get("user_name") or "").strip() or None
        persona_context = args.get("persona_context")
        if persona_context is not None and not isinstance(persona_context, dict):
            persona_context = None
        raw = get_daily_horoscope(sign, dt)
        formatted = format_daily_horoscope_response_with_context(
            raw,
            user_name=user_name,
            persona_context=persona_context,
        )
        return [types.TextContent(type="text", text=formatted)]

    if name == "get_kundli":
        logger.info("Calling get_kundli with args: %s", args)
        dob = str(args.get("date_of_birth") or "").strip()
        tob = str(args.get("time_of_birth") or "12:00").strip()
        place = str(args.get("place") or "").strip()
        if not dob:
            return [types.TextContent(type="text", text="Missing required argument: date_of_birth")]
        if not place and (args.get("latitude") is None or args.get("longitude") is None):
            return [types.TextContent(type="text", text="Missing required argument: place (or latitude+longitude)")]

        lat = args.get("latitude")
        lon = args.get("longitude")
        try:
            lat_f = float(lat) if lat is not None else None
            lon_f = float(lon) if lon is not None else None
        except (ValueError, TypeError):
            return [types.TextContent(type="text", text="Invalid latitude/longitude")]

        result = get_kundli(
            date_of_birth=dob,
            time_of_birth=tob,
            place=place,
            latitude=lat_f,
            longitude=lon_f,
            timezone=str(args.get("timezone") or "").strip() or None,
            ayanamsa=str(args.get("ayanamsa") or "").strip() or None,
            language=str(args.get("language") or "").strip() or None,
            la=str(args.get("la") or "").strip() or None,
            year_length=args.get("year_length"),
            include_dasha_periods=bool(args.get("include_dasha_periods", True)),
            include_mangal_dosha=bool(args.get("include_mangal_dosha", True)),
        )
        return [types.TextContent(type="text", text=format_kundli_response(result))]

    if name in ("get_dasha_details", "get_mangal_dosha_details"):
        logger.info("Calling %s with args: %s", name, args)
        dob = str(args.get("date_of_birth") or "").strip()
        tob = str(args.get("time_of_birth") or "12:00").strip()
        place = str(args.get("place") or "").strip()
        if not dob:
            return [types.TextContent(type="text", text="Missing required argument: date_of_birth")]
        if not place and (args.get("latitude") is None or args.get("longitude") is None):
            return [types.TextContent(type="text", text="Missing required argument: place (or latitude+longitude)")]
        lat = args.get("latitude")
        lon = args.get("longitude")
        try:
            lat_f = float(lat) if lat is not None else None
            lon_f = float(lon) if lon is not None else None
        except (ValueError, TypeError):
            return [types.TextContent(type="text", text="Invalid latitude/longitude")]

        common_kwargs = dict(
            date_of_birth=dob,
            time_of_birth=tob,
            place=place,
            latitude=lat_f,
            longitude=lon_f,
            timezone=str(args.get("timezone") or "").strip() or None,
            ayanamsa=str(args.get("ayanamsa") or "").strip() or None,
            la=str(args.get("la") or "").strip() or None,
        )
        if name == "get_dasha_details":
            result = get_dasha_details(
                **common_kwargs,
                year_length=args.get("year_length"),
            )
            return [types.TextContent(type="text", text=format_dasha_response(result))]

        result = get_mangal_dosha_details(**common_kwargs)
        return [types.TextContent(type="text", text=format_mangal_dosha_response(result))]

    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


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
