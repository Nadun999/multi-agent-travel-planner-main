"""Flight MCP Server — bridges the multi-agent workflow to the Convex flight API.

Exposes four tools over MCP `streamable-http`:
- get_all_flights       list every flight
- search_flights        search by origin + destination (+ optional date)
- book_flight           book a specific flight for a passenger
- get_flight_by_id      fetch one flight by ID

Returns FULL records (airline, flightNumber, origin/destination objects,
flightDate, times, price, currency, availableSeats, etc.) so the agent
and the frontend cards don't need a second lookup.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Flight Service", port=8002, stateless_http=True)

BASE_URL = "https://standing-fish-574.convex.site"


class UpstreamError(Exception):
    """Raised when the Convex upstream is unavailable or returns non-JSON."""


def _get_json(url: str):
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise UpstreamError(f"Flight upstream unreachable: {e}") from e
    except json.JSONDecodeError as e:
        raise UpstreamError(f"Flight upstream returned non-JSON: {e}") from e


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
        raise UpstreamError(f"Flight upstream unreachable: {e}") from e
    except json.JSONDecodeError as e:
        raise UpstreamError(f"Flight upstream returned non-JSON: {e}") from e


def _extract_flights(data) -> list:
    """Normalize the two possible upstream shapes into a list of flight dicts."""
    if isinstance(data, dict) and "flights" in data:
        return data["flights"]
    if isinstance(data, list):
        return data
    return []


def _normalize_code(value: Optional[str]) -> Optional[str]:
    """Uppercase 3-letter IATA airport codes; leave everything else alone."""
    if value and len(value) == 3 and value.isalpha():
        return value.upper()
    return value


@mcp.tool()
def get_all_flights() -> list[dict]:
    """Retrieve every available flight with full details.

    Use this when the user asks to list/browse flights without a specific
    route. Returns a list of flight objects with fields like _id, airline,
    flightNumber, origin (city/airport), destination, flightDate, times,
    price/currency, and availableSeats.
    """
    data = _get_json(f"{BASE_URL}/flights")
    return _extract_flights(data)


@mcp.tool()
def search_flights(
    origin: str,
    destination: str,
    date: Optional[str] = None,
) -> list[dict]:
    """Search flights by origin and destination (with optional date).

    Args:
        origin: Origin city name or 3-letter airport code (e.g., "BOM", "Mumbai").
        destination: Destination city name or 3-letter airport code.
        date: Optional travel date in YYYY-MM-DD.
    """
    params: dict[str, str] = {
        "origin": _normalize_code(origin),
        "destination": _normalize_code(destination),
    }
    if date:
        params["date"] = date
    query = urllib.parse.urlencode(params)
    data = _get_json(f"{BASE_URL}/flights/search?{query}")
    return _extract_flights(data)


@mcp.tool()
def book_flight(
    flight_id: str,
    passenger_name: str,
    passenger_email: str,
) -> dict:
    """Book a specific flight seat.

    Args:
        flight_id: The flight `_id` to book.
        passenger_name: Full name of the passenger.
        passenger_email: Passenger email for the ticket.
    """
    payload = {
        "flightId": flight_id,
        "passengerName": passenger_name,
        "passengerEmail": passenger_email,
    }
    return _post_json(f"{BASE_URL}/flights/book", payload)


@mcp.tool()
def get_flight_by_id(flight_id: str) -> dict:
    """Fetch a single flight record by ID. Useful for booking confirmation."""
    data = _get_json(f"{BASE_URL}/flights/{urllib.parse.quote(flight_id)}")
    if isinstance(data, dict):
        return data
    return {}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
