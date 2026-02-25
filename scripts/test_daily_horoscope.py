#!/usr/bin/env python3
"""
Quick tests for daily horoscope flow: intent, zodiac, and (optional) MCP client.
Run from astro_genie:  python scripts/test_daily_horoscope.py
Or from repo root:     python astro_genie/scripts/test_daily_horoscope.py
"""
import asyncio
import sys
import os

# Ensure astro_genie is on path and cwd so imports (config, agents, mcp_serv) work
_astro_genie = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _astro_genie not in sys.path:
    sys.path.insert(0, _astro_genie)
os.chdir(_astro_genie)


def test_intent():
    print("--- Intent classifier ---")
    from agents.intent_agent import classify
    for msg in ["What is my daily prediction?", "Tell me about my career", "Daily horoscope for today"]:
        intent, params = classify(msg)
        print(f"  {msg!r} -> intent={intent!r} params={params}")


def test_zodiac():
    print("\n--- DOB -> sun sign ---")
    from utils.zodiac import dob_to_sun_sign
    for dob in ["15-03-1995", "25-04-1990", "01-01-2000"]:
        sign = dob_to_sun_sign(dob)
        print(f"  {dob} -> {sign}")


async def test_mcp_client():
    print("\n--- MCP client (requires MCP server on http://127.0.0.1:8001/sse) ---")
    from config import MCP_SERVER_URL
    from mcp_serv.client import call_tool
    try:
        out = await call_tool(MCP_SERVER_URL, "get_daily_horoscope", {"sign": "virgo"})
        if isinstance(out, str) and len(out) > 200:
            print(f"  Got horoscope (length {len(out)}): {out[:200]}...")
        else:
            print(f"  Result: {out}")
    except Exception as e:
        print(f"  Error (is the MCP server running?): {e}")


def main():
    test_intent()
    test_zodiac()
    asyncio.run(test_mcp_client())
    print("\nDone.")


if __name__ == "__main__":
    main()
