"""Hotel MCP Server — bridges the multi-agent workflow to the Convex hotel API.

Exposes four tools over MCP `streamable-http`:
- get_all_hotels        list every hotel
- search_hotels         search by city (+ optional check-in/out)
- book_hotel            book a specific hotel for a guest
- get_hotel_by_id       fetch one hotel by ID (helper for confirmations)

Returns FULL records so the agent (and frontend cards) can use every field
without a second lookup.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Hotel Service", port=8001, stateless_http=True)

BASE_URL = "https://standing-fish-574.convex.site"


class UpstreamError(Exception):
    """Raised when the Convex upstream is unavailable or returns non-JSON.
    FastMCP converts raised exceptions into tool-call errors that the LangGraph
    node can detect and surface as a graceful failure."""


def _get_json(url: str):
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise UpstreamError(f"Hotel upstream unreachable: {e}") from e
    except json.JSONDecodeError as e:
        raise UpstreamError(f"Hotel upstream returned non-JSON: {e}") from e


def _post_json(url: str, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise UpstreamError(f"Hotel upstream unreachable: {e}") from e
    except json.JSONDecodeError as e:
        raise UpstreamError(f"Hotel upstream returned non-JSON: {e}") from e


def _extract_hotels(data) -> list:
    """Normalize the two possible upstream shapes into a list of hotel dicts."""
    if isinstance(data, dict) and "hotels" in data:
        return data["hotels"]
    if isinstance(data, list):
        return data
    return []


@mcp.tool()
def get_all_hotels() -> list[dict]:
    """Retrieve every available hotel with full details.

    Use this when the user asks to list/browse hotels without a specific
    city. Returns a list of hotel objects with fields like _id, name, city,
    pricePerNight, currency, address, and images.
    """
    data = _get_json(f"{BASE_URL}/hotels")
    return _extract_hotels(data)


@mcp.tool()
def search_hotels(
    city: str,
    checkIn: Optional[str] = None,
    checkOut: Optional[str] = None,
) -> list[dict]:
    """Search hotels by city (and optional dates). Returns full records.

    Args:
        city: Hotel city name (e.g., "Bangkok", "Colombo").
        checkIn: Optional check-in date in YYYY-MM-DD.
        checkOut: Optional check-out date in YYYY-MM-DD.
    """
    params: dict[str, str] = {"city": city}
    if checkIn:
        params["checkIn"] = checkIn
    if checkOut:
        params["checkOut"] = checkOut
    query = urllib.parse.urlencode(params)
    data = _get_json(f"{BASE_URL}/hotels/search?{query}")
    return _extract_hotels(data)


@mcp.tool()
def book_hotel(
    hotel_id: str,
    guest_name: str,
    guest_email: str,
    check_in_date: str,
    check_out_date: str,
    room_type: str,
) -> dict:
    """Book a specific hotel room.

    Args:
        hotel_id: The hotel `_id` to book.
        guest_name: Full name of the primary guest.
        guest_email: Guest email for the confirmation.
        check_in_date: Check-in date in YYYY-MM-DD.
        check_out_date: Check-out date in YYYY-MM-DD.
        room_type: One of "single", "double", "suite".
    """
    payload = {
        "hotelId": hotel_id,
        "guestName": guest_name,
        "guestEmail": guest_email,
        "checkInDate": check_in_date,
        "checkOutDate": check_out_date,
        "roomType": room_type,
    }
    return _post_json(f"{BASE_URL}/hotels/book", payload)


@mcp.tool()
def get_hotel_by_id(hotel_id: str) -> dict:
    """Fetch a single hotel record by ID. Useful for booking confirmation."""
    data = _get_json(f"{BASE_URL}/hotels/{urllib.parse.quote(hotel_id)}")
    if isinstance(data, dict):
        return data
    return {}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
