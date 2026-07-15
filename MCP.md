# MCP layer — deep dive

This document explains, in enough detail to defend at the viva, how
TripWeaver's Model Context Protocol integration is put together, why it's
shaped the way it is, and how you'd change it.

## The two MCP servers

Both live in `mcp_servers/`. Each one is a standalone Python process — you
can start them by hand for debugging:

```bash
# Terminal 1
python mcp_servers/hotel_service.py
# Terminal 2
python mcp_servers/flight_service.py
```

Under normal operation you don't have to — `main.py` spawns both as child
subprocesses when the FastAPI app starts (see the `lifespan` context in
`main.py`).

### Hotel service (port 8001)

| MCP tool | Signature | Upstream call |
|---|---|---|
| `get_all_hotels` | `() -> list[dict]` | `GET /hotels` |
| `search_hotels` | `(city, checkIn?, checkOut?) -> list[dict]` | `GET /hotels/search` |
| `book_hotel` | `(hotel_id, guest_name, guest_email, check_in_date, check_out_date, room_type) -> dict` | `POST /hotels/book` |
| `get_hotel_by_id` | `(hotel_id) -> dict` | `GET /hotels/{id}` |

### Flight service (port 8002)

| MCP tool | Signature | Upstream call |
|---|---|---|
| `get_all_flights` | `() -> list[dict]` | `GET /flights` |
| `search_flights` | `(origin, destination, date?) -> list[dict]` | `GET /flights/search` |
| `book_flight` | `(flight_id, passenger_name, passenger_email) -> dict` | `POST /flights/book` |
| `get_flight_by_id` | `(flight_id) -> dict` | `GET /flights/{id}` |

Both servers return **full records** (all fields the upstream provides).
Downstream consumers don't need a second lookup to hydrate a card.

Both wrap upstream errors in a small `UpstreamError` exception. FastMCP
turns that into a tool-call error the LangChain adapter reports as
`ToolMessage(status="error")` — which the agent nodes catch and translate
into a graceful user message.

## The client

`agents/mcp_client.py` is the single point of contact from the agent
process. Its shape:

```python
MCP_SERVERS = {
    "hotel":  {"url": HOTEL_MCP_URL,  "transport": "streamable_http"},
    "flight": {"url": FLIGHT_MCP_URL, "transport": "streamable_http"},
}
```

Environment variables (`HOTEL_MCP_URL`, `FLIGHT_MCP_URL`) override those
URLs so the same code can run against remotely-hosted MCP servers without
touching source. That's the point of the SRS's decoupling requirement.

Two exceptions define the failure surface:

- `MCPToolUnavailable` — the tool name isn't in the catalog (name typo,
  server never connected, catalog stale).
- `MCPToolCallFailed` — the call ran but raised (network error, upstream
  400/500, validation error).

Both are caught in `agents/nodes.py`. Every callable path is wrapped.

## The tool façade

`agents/tools.py` is a stack of one-line async wrappers:

```python
async def search_hotel(city, checkIn=None, checkOut=None):
    kwargs = {"city": city}
    if checkIn: kwargs["checkIn"] = checkIn
    if checkOut: kwargs["checkOut"] = checkOut
    return _unwrap(await call_mcp("search_hotels", **kwargs))
```

`_unwrap` collapses the langchain-mcp-adapters response format — a list of
`{"type": "text", "text": "<json>"}` content blocks — back into the
Python list of dicts the nodes expect. If we later switch to structured
content, the wrapper takes care of it, not the nodes.

Nodes never import `requests`. Nodes never touch a URL. Nodes never
serialize JSON. That's the whole point of the façade.

## The graph

`agents/graph.py`:

```
START ─▶ router ─┬─▶ hotel_node       ─┐
                 ├─▶ flight_node      ─┼─▶ generate_response ─▶ END
                 └─▶ general_qa_node  ─┘
```

- `router` reads the user's message, structured-outputs an intent
  (`hotel` / `flight` / `general`), extracts every relevant entity (city,
  origin, dates, IDs, guest details, `confirm_booking`), and populates
  the shared `GraphState`.
- `hotel_node` and `flight_node` inspect the state, call the right MCP
  tool through the façade, and populate `hotel_results` /
  `flight_results` and/or a booking form / review.
- `general_qa_node` handles anything that isn't a hotel or flight action
  — greetings, destination questions, packing advice — and its LLM
  response is what the frontend streams token-by-token.
- `generate_response` composes the final display text if a node didn't
  already write `response_text` itself.

All node functions are `async`. LangGraph runs them without any special
config — `graph.astream_events(...)` yields both node completions and LLM
token chunks in the same stream.

## Adding a new MCP-backed service

Say you want to add an activities provider (city tours, restaurant
reservations). Concretely:

1. Write `mcp_servers/activity_service.py`. Instantiate `FastMCP` on port
   8003, define a few `@mcp.tool()` functions, and call
   `mcp.run(transport="streamable-http")`.
2. Add one row to `MCP_SERVERS` in `agents/mcp_client.py`:
   ```python
   "activity": {"url": os.getenv("ACTIVITY_MCP_URL", "http://127.0.0.1:8003/mcp"),
                "transport": "streamable_http"},
   ```
3. In `main.py`, add `mcp_servers/activity_service.py` to the
   `_spawn_mcp_servers` list.
4. In `agents/tools.py`, add thin wrappers: `async def
   search_activities(...)` calling `call_mcp("search_activities", ...)`.
5. In `agents/nodes.py`, add an `activity_node`. In `graph.py`, add it
   to the routing.

That's it. No other agent code changes.

## Failure verification

To see the graceful-failure path locally:

```bash
python main.py &                       # start the whole stack
lsof -iTCP:8002 -sTCP:LISTEN           # find the flight MCP pid
kill <flight-mcp-pid>                  # take the flight MCP down
```

Then send `"show me all flights"` in the chat. You'll get:

> The flight service is temporarily unavailable — please try again in a moment. You can still ask general travel questions or search for hotels.

The trace step for `flight_node` will show `status: failed` and the
underlying error message. Hotels and general Q&A stay usable.
