"""LangGraph node functions for TripWeaver.

All external service work is routed through `agents/tools.py` → `mcp_client`
→ the two child MCP servers. Nodes never import `requests`; they never call
a URL. This is the SRS's "agents talk to services only through MCP" line.

Nodes are async because MCP transport is async. The graph is compiled the
same way; LangGraph invokes async nodes natively.
"""

from typing import Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from .entity import GraphState
from .llm import llm
from .mcp_client import MCPToolCallFailed, MCPToolUnavailable
from .prompts import (
    get_system_prompt_for_general_qa,
    get_system_prompt_with_history,
)
from .tools import (
    book_flight,
    book_hotel,
    get_flights,
    get_hotels,
    search_flights,
    search_hotel,
)


class TravelExtraction(BaseModel):
    intent: Literal["hotel", "flight", "general"] = Field(
        default="general",
        description="Main user intent: hotel, flight, or general (general travel Q&A).",
    )

    sub_action: Literal["search", "list_all", "book", "general"] = Field(
        default="general",
        description="Action type: search, list_all, book or general.",
    )

    city: Optional[str] = Field(
        default=None,
        description="Hotel city name. Example: Mumbai, Colombo, Bangkok.",
    )

    check_in: Optional[str] = Field(
        default=None,
        description="Hotel check-in date in YYYY-MM-DD format. Null if not provided.",
    )

    check_out: Optional[str] = Field(
        default=None,
        description="Hotel check-out date in YYYY-MM-DD format. Null if not provided.",
    )

    origin: Optional[str] = Field(
        default=None,
        description="Flight origin city or airport code. Example: BOM, CMB, Mumbai.",
    )

    destination: Optional[str] = Field(
        default=None,
        description="Flight destination city or airport code. Example: DEL, BKK, Delhi.",
    )

    flight_date: Optional[str] = Field(
        default=None,
        description="Flight date in YYYY-MM-DD format. Null if not provided.",
    )

    hotel_id: Optional[str] = Field(
        default=None,
        description="ID of the hotel to book. Null if not provided.",
    )

    guest_name: Optional[str] = Field(
        default=None,
        description="Guest full name for hotel booking. Null if not provided.",
    )

    guest_email: Optional[str] = Field(
        default=None,
        description="Guest email for hotel booking. Null if not provided.",
    )

    room_type: Optional[str] = Field(
        default=None,
        description="Hotel room type such as single, double, or suite. Null if not provided.",
    )

    flight_id: Optional[str] = Field(
        default=None,
        description="ID of the flight to book. Null if not provided.",
    )

    passenger_name: Optional[str] = Field(
        default=None,
        description="Passenger full name for flight booking. Null if not provided.",
    )

    passenger_email: Optional[str] = Field(
        default=None,
        description="Passenger email for flight booking. Null if not provided.",
    )

    confirm_booking: bool = Field(
        default=False,
        description=(
            "True ONLY when the user explicitly confirms they want to finalize "
            "an already-complete booking (e.g. 'yes, confirm', 'place the "
            "booking', 'go ahead and book it'). Merely providing or listing "
            "booking details is NOT confirmation — return false."
        ),
    )


travel_extractor = llm.with_structured_output(TravelExtraction)


# Booking field metadata: (state_key, label, input_type, options)
HOTEL_BOOKING_FIELDS = [
    ("hotel_id", "Hotel ID", "text", None),
    ("check_in", "Check-in date", "date", None),
    ("check_out", "Check-out date", "date", None),
    ("room_type", "Room type", "select", ["single", "double", "suite"]),
    ("guest_name", "Guest full name", "text", None),
    ("guest_email", "Guest email", "email", None),
]

FLIGHT_BOOKING_FIELDS = [
    ("flight_id", "Flight ID", "text", None),
    ("passenger_name", "Passenger full name", "text", None),
    ("passenger_email", "Passenger email", "email", None),
]


def _humanjoin(items: list) -> str:
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _booking_followup(state: dict, fields: list, what: str) -> Optional[str]:
    known = [(label, state.get(name)) for name, label, _, _ in fields if state.get(name)]
    missing = [label for name, label, _, _ in fields if not state.get(name)]

    if not missing:
        return None

    parts = []
    if known:
        summary = ", ".join(f"{label}: {value}" for label, value in known)
        parts.append(f"So far I have {summary}.")
    parts.append(f"To book your {what}, please also provide {_humanjoin(missing)}.")
    return " ".join(parts)


def _booking_form(state: dict, fields: list, kind: str, title: str) -> Optional[dict]:
    if all(state.get(name) for name, _, _, _ in fields):
        return None

    return {
        "kind": kind,
        "title": title,
        "fields": [
            {
                "name": name,
                "label": label,
                "type": input_type,
                "value": state.get(name),
                "options": options,
            }
            for name, label, input_type, options in fields
        ],
    }


def _booking_review(state: dict, fields: list, kind: str, title: str) -> dict:
    return {
        "kind": kind,
        "title": title,
        "items": [
            {"label": label, "value": state.get(name)}
            for name, label, _, _ in fields
        ],
    }


async def router(state: GraphState) -> dict:
    """Intent extraction. Populates state fields consumed by the child nodes."""
    user_message = state["messages"][-1]
    history_messages = state["messages"][:-1]

    system_prompt = get_system_prompt_with_history("\n".join(history_messages))

    invocation_messages = [SystemMessage(content=system_prompt)]
    for i in range(0, len(history_messages), 2):
        invocation_messages.append(HumanMessage(content=history_messages[i]))
        if i + 1 < len(history_messages):
            invocation_messages.append(AIMessage(content=history_messages[i + 1]))
    invocation_messages.append(HumanMessage(content=user_message))

    try:
        extracted = await travel_extractor.ainvoke(invocation_messages)
        data = extracted.dict()
    except Exception:
        data = {
            "intent": "general",
            "sub_action": "general",
            "city": None,
            "check_in": None,
            "check_out": None,
            "origin": None,
            "destination": None,
            "flight_date": None,
            "hotel_id": None,
            "guest_name": None,
            "guest_email": None,
            "room_type": None,
            "flight_id": None,
            "passenger_name": None,
            "passenger_email": None,
            "confirm_booking": False,
        }

    return {
        "intent": data.get("intent", "general"),
        "sub_action": data.get("sub_action", "general"),
        "city": data.get("city"),
        "check_in": data.get("check_in"),
        "check_out": data.get("check_out"),
        "origin": data.get("origin"),
        "destination": data.get("destination"),
        "flight_date": data.get("flight_date"),
        "hotel_id": data.get("hotel_id"),
        "guest_name": data.get("guest_name"),
        "guest_email": data.get("guest_email"),
        "room_type": data.get("room_type"),
        "flight_id": data.get("flight_id"),
        "passenger_name": data.get("passenger_name"),
        "passenger_email": data.get("passenger_email"),
        "confirm_booking": bool(data.get("confirm_booking")),
        "hotel_results": [],
        "flight_results": [],
        "response_text": "",
    }


def _format_hotel(hotel: dict) -> str:
    name = hotel.get("name", "Unknown hotel")

    city_data = hotel.get("city", "unknown city")
    if isinstance(city_data, dict):
        city = city_data.get("name", "unknown city")
    else:
        city = city_data

    stars = hotel.get("stars", hotel.get("rating", "N/A"))
    price = hotel.get("price", hotel.get("pricePerNight", "N/A"))
    currency = hotel.get("currency", "USD")

    available = hotel.get(
        "available_rooms",
        hotel.get("availableRooms", hotel.get("available", "N/A")),
    )

    return (
        f"{name} in {city}, "
        f"{stars} stars - {currency} {price}/night - "
        f"{available} rooms"
    )


def _format_flight(flight: dict) -> str:
    airline = flight.get("airline", "Unknown airline")

    number = flight.get(
        "flightNumber",
        flight.get("flight_number", flight.get("flightNo", "N/A")),
    )

    origin_data = flight.get("origin", "unknown")
    destination_data = flight.get("destination", "unknown")

    if isinstance(origin_data, dict):
        origin = origin_data.get("airport", origin_data.get("city", "unknown"))
    else:
        origin = origin_data

    if isinstance(destination_data, dict):
        destination = destination_data.get("airport", destination_data.get("city", "unknown"))
    else:
        destination = destination_data

    flight_date = flight.get(
        "flightDate",
        flight.get("date", flight.get("departure_date", "unknown")),
    )

    departure_time = flight.get("departureTime", flight.get("departure_time", "N/A"))
    arrival_time = flight.get("arrivalTime", flight.get("arrival_time", "N/A"))

    price = flight.get("price", "N/A")
    currency = flight.get("currency", "USD")

    seats = flight.get(
        "availableSeats",
        flight.get("available_seats", flight.get("seats", "N/A")),
    )

    return (
        f"{airline} {number} from {origin} to {destination} "
        f"on {flight_date}, {departure_time} - {arrival_time} "
        f"- {currency} {price} - {seats} seats"
    )


def _as_list(result, key: str) -> list:
    """Coerce the MCP tool result into a Python list, whichever shape we get."""
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        return result.get(key, [])
    return []


# --- Graceful failure helpers ---------------------------------------------
# Nodes return a `tool_status` field alongside the usual state deltas so the
# tracer / UI can distinguish "external service went bad" (FAILED) from
# "everything worked but there were no matches" (SUCCEEDED, empty).

FAILURE_MSG_HOTEL = (
    "The hotel service is temporarily unavailable — please try again in a moment. "
    "You can still ask general travel questions or search for flights."
)
FAILURE_MSG_FLIGHT = (
    "The flight service is temporarily unavailable — please try again in a moment. "
    "You can still ask general travel questions or search for hotels."
)


def _failure_state(kind: str, exc: Exception) -> dict:
    """Standard shape returned when an MCP call fails."""
    msg = FAILURE_MSG_HOTEL if kind == "hotel" else FAILURE_MSG_FLIGHT
    return {
        "hotel_results": [],
        "flight_results": [],
        "response_text": msg,
        "tool_status": "failed",
        "tool_error": str(exc),
    }


async def hotel_node(state: GraphState) -> dict:
    city = state.get("city")
    check_in = state.get("check_in")
    check_out = state.get("check_out")

    if state.get("sub_action") == "book":
        hotel_id = state.get("hotel_id")

        # No hotel chosen yet — offer options to pick from.
        if not hotel_id:
            if city:
                try:
                    hotels = _as_list(
                        await search_hotel(
                            city=city, checkIn=check_in, checkOut=check_out
                        ),
                        "hotels",
                    )
                except (MCPToolUnavailable, MCPToolCallFailed) as e:
                    return _failure_state("hotel", e)

                if hotels:
                    return {
                        "hotel_results": hotels,
                        "flight_results": [],
                        "response_text": (
                            f"Here are hotels in {city}. Pick one to book, "
                            "or tell me the hotel ID."
                        ),
                    }
                return {
                    "hotel_results": [],
                    "flight_results": [],
                    "response_text": f"I couldn't find hotels in {city}. Try another city.",
                }
            return {
                "hotel_results": [],
                "flight_results": [],
                "response_text": (
                    "Which hotel would you like to book? Tell me the city "
                    "(for example, 'hotels in Bangkok') and I'll show you options "
                    "to choose from."
                ),
            }

        # Hotel chosen — collect the remaining details.
        followup = _booking_followup(state, HOTEL_BOOKING_FIELDS, "hotel")
        if followup:
            return {
                "hotel_results": [],
                "flight_results": [],
                "response_text": followup,
                "booking_form": _booking_form(
                    state, HOTEL_BOOKING_FIELDS, "hotel", "Book your hotel"
                ),
            }

        # All details present — require an explicit confirmation.
        if not state.get("confirm_booking"):
            return {
                "hotel_results": [],
                "flight_results": [],
                "response_text": "Please review your hotel booking and confirm to finalize it.",
                "booking_review": _booking_review(
                    state, HOTEL_BOOKING_FIELDS, "hotel", "Confirm your hotel booking"
                ),
            }

        try:
            result = await book_hotel(
                hotel_id=hotel_id,
                guest_name=state.get("guest_name"),
                guest_email=state.get("guest_email"),
                check_in_date=state.get("check_in"),
                check_out_date=state.get("check_out"),
                room_type=state.get("room_type"),
            )
        except (MCPToolUnavailable, MCPToolCallFailed) as e:
            return _failure_state("hotel", e)

        confirmation = "Hotel booking completed."
        if isinstance(result, dict):
            confirmation = result.get("message") or result.get("status") or confirmation
        return {
            "hotel_results": [],
            "flight_results": [],
            "response_text": confirmation,
        }

    # Non-booking paths: search or list-all.
    try:
        if city:
            result = await search_hotel(city=city, checkIn=check_in, checkOut=check_out)
        else:
            result = await get_hotels()
    except (MCPToolUnavailable, MCPToolCallFailed) as e:
        return _failure_state("hotel", e)

    hotel_results = _as_list(result, "hotels")

    if not hotel_results:
        return {
            "hotel_results": [],
            "flight_results": [],
            "response_text": (
                "I couldn't find any hotels. "
                "Try searching by city, for example: 'available hotels in Mumbai'."
            ),
        }

    return {
        "hotel_results": hotel_results,
        "flight_results": [],
        "response_text": "",
    }


async def flight_node(state: GraphState) -> dict:
    origin = state.get("origin")
    destination = state.get("destination")
    flight_date = state.get("flight_date")

    if state.get("sub_action") == "book":
        flight_id = state.get("flight_id")

        # No flight chosen yet — offer options to pick from.
        if not flight_id:
            if origin and destination:
                try:
                    flights = _as_list(
                        await search_flights(
                            origin=origin, destination=destination, date=flight_date
                        ),
                        "flights",
                    )
                except (MCPToolUnavailable, MCPToolCallFailed) as e:
                    return _failure_state("flight", e)

                if flights:
                    return {
                        "hotel_results": [],
                        "flight_results": flights,
                        "response_text": (
                            f"Here are flights from {origin} to {destination}. "
                            "Pick one to book, or tell me the flight ID."
                        ),
                    }
                return {
                    "hotel_results": [],
                    "flight_results": [],
                    "response_text": (
                        f"I couldn't find flights from {origin} to {destination}. "
                        "Try another route."
                    ),
                }
            return {
                "hotel_results": [],
                "flight_results": [],
                "response_text": (
                    "Which flight would you like to book? Tell me the route "
                    "(for example, 'flights from Mumbai to Delhi') and I'll show "
                    "you the options to choose from."
                ),
            }

        # Flight chosen — collect passenger details.
        followup = _booking_followup(state, FLIGHT_BOOKING_FIELDS, "flight")
        if followup:
            return {
                "hotel_results": [],
                "flight_results": [],
                "response_text": followup,
                "booking_form": _booking_form(
                    state, FLIGHT_BOOKING_FIELDS, "flight", "Book your flight"
                ),
            }

        # Confirmation gate.
        if not state.get("confirm_booking"):
            return {
                "hotel_results": [],
                "flight_results": [],
                "response_text": "Please review your flight booking and confirm to finalize it.",
                "booking_review": _booking_review(
                    state, FLIGHT_BOOKING_FIELDS, "flight", "Confirm your flight booking"
                ),
            }

        try:
            result = await book_flight(
                flight_id=flight_id,
                passenger_name=state.get("passenger_name"),
                passenger_email=state.get("passenger_email"),
            )
        except (MCPToolUnavailable, MCPToolCallFailed) as e:
            return _failure_state("flight", e)

        confirmation = "Flight booking completed."
        if isinstance(result, dict):
            confirmation = result.get("message") or result.get("status") or confirmation
        return {
            "hotel_results": [],
            "flight_results": [],
            "response_text": confirmation,
        }

    # Non-booking paths.
    if origin and destination:
        try:
            result = await search_flights(origin=origin, destination=destination, date=flight_date)
        except (MCPToolUnavailable, MCPToolCallFailed) as e:
            return _failure_state("flight", e)
    elif origin or destination:
        return {
            "hotel_results": [],
            "flight_results": [],
            "response_text": (
                "I need both departure and destination information. "
                "For example: 'flight from BOM to DEL'."
            ),
        }
    else:
        try:
            result = await get_flights()
        except (MCPToolUnavailable, MCPToolCallFailed) as e:
            return _failure_state("flight", e)

    flight_results = _as_list(result, "flights")

    if not flight_results:
        return {
            "hotel_results": [],
            "flight_results": [],
            "response_text": (
                "I couldn't find flights matching your request. "
                "Try another route or ask for all flights."
            ),
        }

    return {
        "hotel_results": [],
        "flight_results": flight_results,
        "response_text": "",
    }


async def general_qa_node(state: GraphState) -> dict:
    """General travel Q&A agent — for questions that aren't a hotel or flight
    lookup/booking (destinations, visas, packing, weather guidance, etc.)."""
    user_message = state["messages"][-1]
    history_messages = state["messages"][:-1]

    system_prompt = get_system_prompt_for_general_qa("\n".join(history_messages))

    invocation_messages = [SystemMessage(content=system_prompt)]
    for i in range(0, len(history_messages), 2):
        invocation_messages.append(HumanMessage(content=history_messages[i]))
        if i + 1 < len(history_messages):
            invocation_messages.append(AIMessage(content=history_messages[i + 1]))
    invocation_messages.append(HumanMessage(content=user_message))

    try:
        response = await llm.ainvoke(invocation_messages)
        return {
            "hotel_results": [],
            "flight_results": [],
            "response_text": response.content,
        }

    except Exception as e:
        return {
            "hotel_results": [],
            "flight_results": [],
            "response_text": f"I couldn't understand your request clearly. Error: {str(e)}",
        }


async def generate_response(state: GraphState) -> dict:
    if state.get("response_text"):
        return {"response_text": state["response_text"]}

    hotel_results = state.get("hotel_results", [])
    flight_results = state.get("flight_results", [])

    if hotel_results:
        count = len(hotel_results)
        lines = [_format_hotel(hotel) for hotel in hotel_results[:5]]
        return {
            "response_text": (
                f"I found {count} hotel option{'s' if count != 1 else ''}:\n"
                + "\n".join(lines)
            )
        }

    if flight_results:
        count = len(flight_results)
        lines = [_format_flight(flight) for flight in flight_results[:5]]
        return {
            "response_text": (
                f"I found {count} flight option{'s' if count != 1 else ''}:\n"
                + "\n".join(lines)
            )
        }

    return {"response_text": "I couldn't find matching travel options."}


def route_after_extraction(state: GraphState) -> str:
    intent = state.get("intent", "general")

    if intent == "hotel":
        return "hotel"

    if intent == "flight":
        return "flight"

    return "general"
