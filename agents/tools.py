"""Tools façade — thin async wrappers that dispatch to MCP tools.

Every function here calls exactly one MCP tool (living in mcp_servers/) and
returns a normalized Python value. Nodes only import these names.

Return-shape notes
------------------
langchain-mcp-adapters returns tool output as a list of LangChain content
blocks. For structured JSON output (our list[dict] tools), each record
comes back as its own text block:
    {"type": "text", "text": "<json>"}
`_unwrap` collapses that back into the Python object the nodes expect.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from .mcp_client import call_mcp


def _unwrap(raw: Any) -> Any:
    """Turn a langchain-mcp-adapters tool result into a Python object.

    Handles four shapes:
      1. List of text blocks (one JSON object each) → parse each, collect.
      2. Single text block → parse its `text`.
      3. Raw JSON string → parse.
      4. Already a Python list/dict/primitive → return as-is.

    Anything that fails to parse falls through as-is; upstream code decides
    whether that's an error or just an unusual result.
    """
    # (4) primitive / already-parsed
    if raw is None or isinstance(raw, (dict, int, float, bool)):
        return raw

    # (1, 2) list of text blocks
    if isinstance(raw, list):
        # Detect content-block shape by looking at the first element.
        if raw and isinstance(raw[0], dict) and raw[0].get("type") == "text":
            parsed: list[Any] = []
            for block in raw:
                text = block.get("text", "") if isinstance(block, dict) else ""
                try:
                    parsed.append(json.loads(text))
                except (json.JSONDecodeError, TypeError):
                    parsed.append(text)
            # Single-block responses aren't lists at the semantic level — a
            # book_hotel result comes back as one block wrapping one dict.
            if len(parsed) == 1 and not isinstance(parsed[0], list):
                return parsed[0]
            return parsed
        # A list of already-parsed items — return as-is.
        return raw

    # (3) raw string
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    return raw


# ---- Hotel tools -----------------------------------------------------

async def get_hotels() -> Any:
    """List every hotel (full records)."""
    return _unwrap(await call_mcp("get_all_hotels"))


async def search_hotel(
    city: str,
    checkIn: Optional[str] = None,
    checkOut: Optional[str] = None,
) -> Any:
    """Search hotels by city (+ optional dates)."""
    kwargs: dict[str, Any] = {"city": city}
    if checkIn:
        kwargs["checkIn"] = checkIn
    if checkOut:
        kwargs["checkOut"] = checkOut
    return _unwrap(await call_mcp("search_hotels", **kwargs))


async def book_hotel(
    hotel_id: str,
    guest_name: str,
    guest_email: str,
    check_in_date: str,
    check_out_date: str,
    room_type: str,
) -> Any:
    """Book a hotel."""
    return _unwrap(
        await call_mcp(
            "book_hotel",
            hotel_id=hotel_id,
            guest_name=guest_name,
            guest_email=guest_email,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            room_type=room_type,
        )
    )


# ---- Flight tools ----------------------------------------------------

async def get_flights() -> Any:
    """List every flight (full records)."""
    return _unwrap(await call_mcp("get_all_flights"))


async def search_flights(
    origin: str,
    destination: str,
    date: Optional[str] = None,
) -> Any:
    """Search flights by origin + destination (+ optional date)."""
    kwargs: dict[str, Any] = {"origin": origin, "destination": destination}
    if date:
        kwargs["date"] = date
    return _unwrap(await call_mcp("search_flights", **kwargs))


async def book_flight(
    flight_id: str,
    passenger_name: str,
    passenger_email: str,
) -> Any:
    """Book a flight."""
    return _unwrap(
        await call_mcp(
            "book_flight",
            flight_id=flight_id,
            passenger_name=passenger_name,
            passenger_email=passenger_email,
        )
    )
